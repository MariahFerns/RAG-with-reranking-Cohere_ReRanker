# -*- coding: utf-8 -*-
"""Cohere_ReRanker.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1rM7unGrIS00zbgJ7HKp3gWB9Hh-ERIsh
"""

# Import required libraries
import cohere
import wikipedia
from langchain_text_splitters import RecursiveCharacterTextSplitter
import streamlit as st
import numpy as np
import sklearn

def generate_response(api_key, question):

  # Initialize the Cohere client with api key
  co = cohere.Client(api_key)

  # Fetch wikipedia article on machine learning

  article = wikipedia.page('MachineLearning')
  # store content of article
  text = article.content


  # Perform text splitting into chunks

  text_splitter = RecursiveCharacterTextSplitter(
      chunk_size = 512,
      chunk_overlap = 50,
      length_function = len,
      is_separator_regex = False,
  )

  # create list of document objects which are chunks

  chunks_1 = text_splitter.create_documents([text])
  chunks = [ chunk.page_content for chunk in chunks_1 ]



  # 1. EMBEDDING
  # Compute embeddings for each chunk

  model = 'embed-english-v3.0' # Cohere's embedding model

  response = co.embed(
      texts = chunks,
      model = model,
      input_type = 'search_document', # text being embedded are the chunks we want to search over
      embedding_types = ['float'],
  )


  # create embeddings list
  embeddings = response.embeddings.float


  # Store embeddings in a vector database
  # using a simple vector DB: python dict where keys are indexes of chunks & values are numpy arrays of embeddings

  vector_db = { i: np.array(embedding) for i, embedding in enumerate(embeddings)}


  # Get the question from the user

  question = question


  # Convert question to embeddings as well
  response = co.embed(
      texts = [question],
      model = model,
      input_type = 'search_query', # i/p type is now search_query as we are passing the question to be embedded
      embedding_types = ['float'],
  )

  question_embedding = response.embeddings.float[0]



  # 2. RETRIEVAL

  # To find similarity between query embeddings and chunk embeddings, use Cosine similarity

  from sklearn.metrics.pairwise import cosine_similarity

  # Define a function to compute similarity using sklearn cosine_similarity
  def cos_sim(a, b):
    # converting to array and reshaping to pass to sklearn's cosine_similarity funciton
    a = np.array(a)
    b = np.array(b)
    a = a.reshape(1, -1)
    b = b.reshape(1, -1)

    similarities = cosine_similarity(a, b)

    return similarities.reshape(1)


  # calculate similarity between user question and each chunk
  similarities_arr = [ cos_sim(question_embedding, chunk) for chunk in embeddings ]


  # convert the list of scalar arrays to a simple list
  similarities=[]
  [ similarities.extend(arr) for arr in similarities_arr ]


  # Sort in descending order of similarity
  sorted_indices = np.argsort(similarities)[::-1]
  sorted_indices
  # store only top 10 indices
  top_indices = sorted_indices[:10]


  # # Retrieve the top 10 most similar chunks
  top_chunks = [ chunks[index.item()] for index in top_indices ]


  # 3. RE-RANKING

  # Reranking the top 10 chunks to get the 3 most relevant chunks

  response = co.rerank(
      model = 'rerank-english-v2.0', # using Cohere's rerank model
      query = question,
      documents = top_chunks,
      top_n = 3,
      return_documents = True,
  )


  top_reranked_chunks = [ result.document.text  for result in response.results ]



  # 4. GENERATION

  # Generate the final response using Cohere's command model

  # give instructions about task and desired style of output
  preamble = '''
  ## Task and context
  You help people answer questions on a wide range of topics interactively.
  You are equipped with search engines and the internet that you can use to research your answer.
  Your response should be focused on answering the question in a step by step manner that is concise and clear.

  ## Style Guide
  Answer in full sentences unless the user asks for a different style of response.
  '''

  # storing top chunks
  documents = [
      {'title': 'chunk-0', 'snippet':top_reranked_chunks[0]},
      {'title': 'chunk-1', 'snippet':top_reranked_chunks[1]},
      {'title': 'chunk-2', 'snippet':top_reranked_chunks[2]},
  ]


  # 4. GENERATION
  # generate the reponse again using top 3 most relevant chunk as the source
  response = co.chat(
      model = 'command-r',
      message = question,
      documents = documents,
      preamble = preamble,
      temperature = 0.3,
  )

  return response.text



## Building the streamlit web interface

st.title('🔖RAG with Re-Ranking')

st.text_area(
    '''
    This app refers to the Wikipedia page on Machine Learning.
    Ask a question pertaining to this topic to get the response.
    The responses are re-ranked using Cohere's rerank model to fetch
    the most relevant responses to your question.
    '''
)

# get api key
result=[]
with st.form('form', clear_on_submit=True):
  question = st.text_area('Enter your question pertaining to Machine Learning: ', height=200)

  cohere_api_key = st.text_input('Enter your Cohere API key: ', type='password')
  submit = st.form_submit_button('Submit')

  if (submit and cohere_api_key and question):
    with st.spinner('Retrieving reponse...'):
      response = generate_response(cohere_api_key, question)
      result.append(response)
      del cohere_api_key

# Print the response
if len(result):
  st.info(response)
