import pandas as pd
import pickle
import re
from io import BytesIO
import joblib

### Importing libraries
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from nltk.stem.porter import PorterStemmer

from flask import session

### Preprocessing Function
ps = PorterStemmer()

class MovieReviewClassifier:
  def __init__(self):
    pass

  def read_data(self):
    return pd.read_csv("./data/IMDB Dataset.csv", header=None, skiprows=1, names=['review', 'sentiment'])
  
  def preprocess(self, text):
      text = text.strip()
      text = re.sub("<[^>]*>", "",text)    
      text = re.sub('[^a-zA-Z]', ' ',text)
      text = text.lower()
      text = text.split()
      text = [ps.stem(word) for word in text]
      text = ' '.join(text)
      return text
      
  def preprocess_data(self, df):
    print("Processing data")
    df['Preprocessed_review'] = df['review'].apply(self.preprocess)
    map_dict = {'positive':1,'negative':0}
    df['sentiment_numeric'] = df.sentiment.map(map_dict)
    return df

  def get_model(self):
    print("Preparing model pipeline")
    pipeline = Pipeline([
        ('tfidf',TfidfVectorizer()),        
        ('log_reg', LogisticRegression())         
    ])
    return pipeline
  
  def train_data(self):
    print('Started Training')
    try:
      df = self.read_data()
      df = self.preprocess_data(df)
      x_train, y_train = df.Preprocessed_review, df.sentiment_numeric
      model = self.get_model()
      model.fit(x_train, y_train)
      with open('model/model.pkl', 'wb') as model_file:
        pickle.dump(model, model_file)
      print('completed training')
    except Exception as e:
      print(e)
  
  def infer(self, test_data):
    print('Predicting data')
    try:
      print('Loading model from DB')
      with open('model/model.pkl', 'rb') as model_file:
        model = pickle.load(model_file)
        if model:
          test_data = self.preprocess(test_data)
          pred = model.predict([test_data])[0]
          review_map ={0:"Negative", 1:"Positive"}
          return review_map[pred]
        else:
          return "No model exist! Train the data"
    except Exception as exc:
      return f'Exception : exc'
