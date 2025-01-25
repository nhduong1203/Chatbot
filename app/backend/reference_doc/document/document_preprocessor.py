import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

class TextPreprocessor:
    def __init__(self):
        # Ensure necessary NLTK resources are downloaded
        nltk.download('punkt', quiet=True)
        nltk.download('wordnet', quiet=True)
        nltk.download('averaged_perceptron_tagger', quiet=True)
        nltk.download('stopwords', quiet=True)
        nltk.download('punkt_tab', quiet=True)

        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(stopwords.words('english'))


    def preprocess(self, text: str, stop_word=False, apply_lemmatize=True) -> str:
        """
        Preprocess a single chunk of text: tokenize, remove stopwords, lemmatize, and optionally stem.
        """

        # Tokenize into words
        words = word_tokenize(text)
        
        # Remove stopwords
        if stop_word:
            words = [word for word in words if word.lower() not in self.stop_words]

        # Apply lemmatization
        if apply_lemmatize:
            words = [self.lemmatizer.lemmatize(word) for word in words]

        return ' '.join(words)