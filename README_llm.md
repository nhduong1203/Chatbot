# Serving LLM Model using TensorRT-LLM, Triton Inference Serve and Kserve

## Building TensorRT-LLM engine

### TensorRT-LLM Introduction 

TensorRT-LLM is an optimized library developed by NVIDIA for accelerating large language model (LLM) inference on GPUs. It leverages TensorRT's highly efficient kernel fusion, precision calibration, and multi-GPU scaling to provide fast and memory-efficient execution. By using TensorRT-LLM, we can achieve significant performance improvements in both latency and throughput compared to traditional deep learning frameworks.

In this project, we will use `meta-llama/Llama-3.1-8B-Instruct` as our LLM model.

### Creating a Google Persistent Disk to Store the TensorRT-LLM Engine Output

**Create a Disk**
```sh
gcloud compute disks create my-disk \
    --size=150GB \ 
    --type=pd-ssd \  
    --zone=CLUSTER_ZONE 
```

Attach the disk to the GPU instance:
```sh
gcloud compute instances attach-disk GPU_INSTANCE \
    --disk=my-disk \
    --zone=CLUSTER_ZONE
```

**Format the Disk (if needed)**
If the newly created disk does not have a filesystem, format it first. SSH into the GPU instance and run:
```sh
sudo mkfs.ext4 /dev/sdb
```

**Create a Mount Point Directory**
Choose a directory to mount the disk, e.g., `/mnt/models`:
```sh
sudo mkdir -p /mnt/models
```

**Mount the Disk**
Run the following command to mount the disk:
```sh
sudo mount /dev/sdb /mnt/models
```

### Building the TensorRT-LLM Engine

This process requires a GPU. SSH into the GPU instance before proceeding.

**Clone the TensorRT-LLM Repository**
```sh
git clone https://github.com/NVIDIA/TensorRT-LLM.git
cd TensorRT-LLM
git submodule update --init --recursive
git lfs pull
cd examples/llama
pip install --upgrade -r requirements.txt --extra-index-url https://pypi.nvidia.com
```

**Download Llama Model**
```sh
huggingface-cli login
huggingface-cli download meta-llama/Llama-3.1-8B-Instruct --local-dir ./checkpoints/
```
The model will be stored in `TensorRT-LLM/examples/llama/checkpoints/Llama-3.1-8B-Instruct`

**Convert Model to TensorRT-LLM Checkpoint Format**
```sh
python convert_checkpoint.py --model_dir ./checkpoints/Llama-3.1-8B-Instruct \
                              --output_dir tmp \
                              --dtype float16
```

**Build the TensorRT-LLM Engine**
```sh
trtllm-build --checkpoint_dir ./tmp \
             --output_dir ./engines \
             --gemm_plugin float16 \
             --max_batch_size 1 \
             --max_num_tokens 4096 \
             --max_input_len 16384 \
             --max_seq_len 16384 \
             --max_beam_width 3 \
             --reduce_fusion enable \
             --multiple_profiles enable \
             --use_paged_context_fmha enable
```
The TensorRT-LLM engine will be stored at `TensorRT-LLM/examples/llama/engines`

**Copy Model and Engine to Google Persistent Disk (GPD)**
```sh
cp -r TensorRT-LLM/examples/llama/checkpoints/Llama-3.1-8B-Instruct /mnt/models/
cp -r TensorRT-LLM/examples/llama/engines /mnt/models/
```

This completes the setup for building and storing the TensorRT-LLM engine.

**Create `run_triton.sh`**

This script is responsible for running the Triton TensorRT-LLM backend.

```sh
cd /mnt/models/

cat << 'EOF' > run_triton.sh
#!/bin/sh

set -e

export TRT_BACKEND_DIR=/root/tensorrtllm_backend

echo "Cloning tensorrtllm_backend..."
if [ -d "$TRT_BACKEND_DIR" ]; then
  echo "Directory $TRT_BACKEND_DIR exists, skipping clone."
else
  cd /root
  git clone -b v0.12.0 https://github.com/triton-inference-server/tensorrtllm_backend.git
  cd $TRT_BACKEND_DIR
  git lfs install
  git lfs pull
fi

# Configure model
echo "Configuring model..."
cd $TRT_BACKEND_DIR
cp -r all_models/inflight_batcher_llm/ llama_ifb

export HF_LLAMA_MODEL=/mnt/models/Llama-3.1-8B-Instruct/
export ENGINE_PATH=/mnt/models/engines/

python3 tools/fill_template.py -i llama_ifb/preprocessing/config.pbtxt tokenizer_dir:${HF_LLAMA_MODEL},triton_max_batch_size:64,preprocessing_instance_count:1
python3 tools/fill_template.py -i llama_ifb/postprocessing/config.pbtxt tokenizer_dir:${HF_LLAMA_MODEL},triton_max_batch_size:64,postprocessing_instance_count:1
python3 tools/fill_template.py -i llama_ifb/tensorrt_llm_bls/config.pbtxt triton_max_batch_size:64,decoupled_mode:False,bls_instance_count:1,accumulate_tokens:False,logits_datatype:TYPE_FP32
python3 tools/fill_template.py -i llama_ifb/ensemble/config.pbtxt triton_max_batch_size:64,logits_datatype:TYPE_FP32
python3 tools/fill_template.py -i llama_ifb/tensorrt_llm/config.pbtxt triton_backend:tensorrtllm,triton_max_batch_size:64,decoupled_mode:False,max_beam_width:1,engine_dir:${ENGINE_PATH},max_tokens_in_paged_kv_cache:2560,max_attention_window_size:2560,kv_cache_free_gpu_mem_fraction:0.5,exclude_input_in_output:True,enable_kv_cache_reuse:False,batching_strategy:inflight_fused_batching,max_queue_delay_microseconds:0,encoder_input_features_data_type:TYPE_FP16,logits_datatype:TYPE_FP32

# Run Triton Server
echo "Running Triton Server..."
pip install SentencePiece
tritonserver --model-repository=$TRT_BACKEND_DIR/llama_ifb --http-port=8080 --grpc-port=9000 --metrics-port=8002 --disable-auto-complete-config --backend-config=python,shm-region-prefix-name=prefix0_
EOF
```

This completes the setup for building, storing, and running the TensorRT-LLM engine with Triton Inference Server.

### Create PV/PVC for our Google Persistent Disk
We will create a PersistentVolume (PV) and PersistentVolumeClaim (PVC) to bind our GPD so that the upcoming Pod can use TensorRT-LLM output.

```sh
kubectl apply -f- << EOF
apiVersion: v1
kind: PersistentVolume
metadata:
  name: gke-pd-pv
spec:
  capacity:
    storage: 150Gi  
  accessModes:
    - ReadWriteOnce 
  persistentVolumeReclaimPolicy: Retain
  storageClassName: standard 
  gcePersistentDisk:
    pdName: my-disk
    fsType: ext4
EOF

kubectl apply -f- << EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: gke-pd-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 150Gi
  storageClassName: standard 
EOF
```

## Serving with Triton Backend and KServe

### Introduction

**Triton Inference Server** developed by NVIDIA, is an open-source tool optimized for deploying AI models efficiently on GPUs. It supports multiple frameworks and features like dynamic batching and concurrent execution, making it ideal for large-scale inference.

**KServe** is a Kubernetes-native solution for serving ML models at scale. It simplifies model deployment with auto-scaling, multi-framework support, and seamless integration with inference engines like Triton.

To install KServe on your Google Kubernetes Engine (GKE) cluster, follow the official tutorial: [Install KServe on GKE](https://kserve.github.io/website/master/admin/serverless/serverless/#4-install-kserve)

### Create a ClusterServerRuntime

```sh
kubectl apply -f- <<EOF
apiVersion: serving.kserve.io/v1alpha1
kind: ClusterServingRuntime
metadata:
  name: triton-trtllm
spec:
  annotations:
    prometheus.kserve.io/path: /metrics
    prometheus.kserve.io/port: "8002"
  containers:
  - args:
    - tritonserver
    - --model-store=/mnt/models/
    - --grpc-port=9000
    - --http-port=8080
    - --allow-grpc=true
    - --allow-http=true
    image: nvcr.io/nvidia/tritonserver:25.01-trtllm-python-py3
    name: kserve-container
    resources:
      requests:
        cpu: "4"
        memory: 12Gi
  protocolVersions:
  - v2
  - grpc-v2
  supportedModelFormats:
  - name: triton
    version: "2"
EOF
```

**ClusterServingRuntime** in KServe is a configuration that defines how to deploy and manage model inference services in a Kubernetes cluster. It allows users to specify resource limits, scaling behavior, and health checks for model serving.

For LLM inference with TensorRT-LLM, a dedicated runtime environment is configured using ClusterServingRuntime. It includes ECI-related annotations (e.g., k8s.aliyun.com/eci-use-specs for specifying GPU instance types and k8s.aliyun.com/eci-auto-imc for enabling ImageCache) to ensure efficient execution on GPU-accelerated Elastic Container Instances (ECI).

**Note:** Check your based image (and choose another image if needed) at  [Triton Server](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/tritonserver/layers) to ensure it uses the same `tensorrt_llm` version as the one used to build your engine.

### Deploy Kserve application

```sh
kubectl apply -f- << EOF
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
 name: llama
spec:
  predictor:
    model:
      modelFormat:
        name: triton
        version: "2"
      runtime: triton-trtllm
      storageUri: pvc://gke-pd-pvc/
      name: kserve-container
      resources:
        limits:
          nvidia.com/gpu: "1"
        requests:
          cpu: "4"
          memory: 12Gi
          nvidia.com/gpu: "1"
      command:
      - sh
      - -c
      - /mnt/models/run_triton.sh
EOF
```

**InferenceService** is a key CRD in KServe that is used to define and manage AI inference services in a cloud-native environment. In the preceding InferenceService, the runtime field is used to bind the preceding ClusterServingRuntime, and storageUri is used to declare the PVC where the model and the model compilation script are located.

You can check whether the application is ready by executing the following command.

```sh
kubectl get isvc llama
```

### Access the application

After the LLM inference service is ready, you can obtain the IP address of the ASM gateway and access the LLM service through it. You also need to store this IP address in your environment file under the `ASM_GATEWAY_IP` key.

```
ASM_GATEWAY_IP=`kubectl -n istio-system get svc istio-ingressgateway -ojsonpath='{.status.loadBalancer.ingress[0].ip}'`

curl -H "Host: llama.default.example.com" -H "Content-Type: application/json" \
http://$ASM_GATEWAY_IP:80/v2/models/ensemble/generate \
-d '{"text_input": "Who is considered the greatest basketball player of all time?", "max_tokens": 30, "bad_words": "", "stop_words": "", "pad_id": 2, "end_id": 2}'
```

**Expected output:**

```
{
  "context_logits": 0.0,
  "cum_log_probs": 0.0,
  "generation_logits": 0.0,
  "model_name": "ensemble",
  "model_version": "1",
  "output_log_probs": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
  "sequence_end": false,
  "sequence_id": 0,
  "sequence_start": false,
  "text_output": "Many consider Michael Jordan the greatest basketball player of all time due to his six NBA championships."
}
```

