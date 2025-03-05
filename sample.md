# Serving LLM Model using TensorRT-LLM, Triton Inference Server, and KServe

## ⚙️ Building TensorRT-LLM Engine

### 💡 TensorRT-LLM Introduction
TensorRT-LLM is an optimized library developed by NVIDIA for accelerating large language model (LLM) inference on GPUs. It leverages TensorRT's highly efficient kernel fusion, precision calibration, and multi-GPU scaling to provide fast and memory-efficient execution.

For this project, we will use `meta-llama/Llama-3.1-8B-Instruct` as our LLM model.

### 🏡 Creating a Google Persistent Disk (GPD)

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
```sh
sudo mkfs.ext4 /dev/sdb
```

**Mount the Disk**
```sh
sudo mkdir -p /mnt/models
sudo mount /dev/sdb /mnt/models
```

### 🔨 Building the TensorRT-LLM Engine

**Clone TensorRT-LLM Repository**
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

**Convert Model to TensorRT-LLM Format**
```sh
python convert_checkpoint.py --model_dir ./checkpoints/Llama-3.1-8B-Instruct \
                              --output_dir tmp \
                              --dtype float16
```

**Build TensorRT-LLM Engine**
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

Copy the model and engine to GPD:
```sh
cp -r TensorRT-LLM/examples/llama/checkpoints/Llama-3.1-8B-Instruct /mnt/models/
cp -r TensorRT-LLM/examples/llama/engines /mnt/models/
```

### 🌐 Deploying with Triton and KServe

#### 🛠️ Create PV/PVC for Google Persistent Disk
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

#### 🕹️ Create ClusterServerRuntime for KServe
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

#### 🌐 Deploy KServe Application
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

#### 🌐 Access the Application
```sh
ASM_GATEWAY_IP=`kubectl -n istio-system get svc istio-ingressgateway -ojsonpath='{.status.loadBalancer.ingress[0].ip}'`

curl -H "Host: llama.default.example.com" -H "Content-Type: application/json" \
http://$ASM_GATEWAY_IP:80/v2/models/ensemble/generate \
-d '{"text_input": "Who is considered the greatest basketball player of all time?", "max_tokens": 30, "bad_words": "", "stop_words": "", "pad_id": 2, "end_id": 2}'
```

Expected output:
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


