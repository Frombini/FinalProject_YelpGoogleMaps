import pandas as pd
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from google.cloud import bigquery
from datetime import timedelta,datetime
import torch
from google.cloud import storage
from io import StringIO
import os
from flask import Flask
from io import BytesIO

project_id = 'final-project-data-insght-pro'
dataset_id = 'ultabeautyreviews'
table_idY = 'yelp_reviews_ulta_beauty'
table_idG = 'google_reviews_ulta_beauty'
client = bigquery.Client()



def analyze_sentiment(review):
    print('tokenizando el texto')
    model = AutoModelForSequenceClassification.from_pretrained("Kaludi/Reviews-Sentiment-Analysis", use_auth_token=False)
    tokenizer = AutoTokenizer.from_pretrained("Kaludi/Reviews-Sentiment-Analysis", use_auth_token=False)
    print('Analizando el sentimiento')
    inputs = tokenizer(review, return_tensors="pt")
    outputs = model(**inputs)
    predicted_label = torch.argmax(outputs.logits, dim=1).item()
    return predicted_label
# Apply sentiment analysis to the 'text' column
def agregar_columnas_sentimientos(df):
    df['sentiment'] = df['text'].apply(lambda x: analyze_sentiment(x))
    df['sentiment_label'] = df['sentiment'].apply(lambda x: 'positive' if x == 1 else 'negative')
    df['hour'] = df['hour'].astype(str).str.split(':').str[0].astype(int)
    return df

def writetobigquery(df,table_id):
    job_config0 = bigquery.LoadJobConfig(write_disposition = 'WRITE_APPEND',create_disposition= 'CREATE_IF_NEEDED')
    client.load_table_from_dataframe(df,'final-project-data-insght-pro.ultabeautyreviews.'+table_id, job_config=job_config0,)

def querys_bigquery(source):

    year_today=datetime.now().year
    year_last_week=(datetime.now()-timedelta(8)).year
    month_last_week=(datetime.now()-timedelta(8)).month
    month_today=datetime.now().month
    if year_today!=year_last_week:
        query_sentiment_analisis_last_year=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.ulta_beauty_sentiment_analysis` where year={year_last_week} and month =12 and source='{source}'"
        query_sentiment_analisis_current_year=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.ulta_beauty_sentiment_analysis` where year={year_today} and month =1 and source'{source}'"
        query_reviews_last_year=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.google_reviews_ulta_beauty` where year={year_last_week} and month =12 and source='{source}'"
        query_reviews_current_year=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.google_reviews_ulta_beauty` where year={year_today} and month =1 and source='{source}'"
        querys={'analisis sentimientos':[query_sentiment_analisis_last_year,query_sentiment_analisis_current_year],'reviews':[query_reviews_last_year,query_reviews_current_year]}
    if year_today==year_last_week:
        if month_today!=month_last_week:
            query_sentiment_analisis_last_month=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.ulta_beauty_sentiment_analysis` where year={year_today} and month ={month_last_week} and source='{source}'"
            query_sentiment_analisis_current_month=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.ulta_beauty_sentiment_analysis` where year={year_today} and month ={month_today} and source='{source}'"
            query_reviews_last_month=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.google_reviews_ulta_beauty` where year={year_today} and month ={month_last_week} and source='{source}'"
            query_reviews_current_month=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.google_reviews_ulta_beauty` where year={year_today} and month ={month_today} and source='{source}'"
            querys={'analisis_sentimientos':[query_sentiment_analisis_last_month,query_sentiment_analisis_current_month],'reviews':[query_reviews_last_month,query_reviews_current_month]}
        if month_today==month_last_week:
            query_sentiment_analisis=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.ulta_beauty_sentiment_analysis` where year={year_today} and month ={month_today} and source='{source}'"
            query_reviews=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.google_reviews_ulta_beauty` where year={year_today} and month ={month_today} and source='{source}'"
            querys={'analisis_sentimientos':query_sentiment_analisis,'reviews':query_reviews}
    return querys
def analisis(querys):
    if len(querys)==2:
        #aqui hace la query
        query_job = client.query(querys['analisis_sentimientos'])
        res_query_analisis_sentimientos=query_job.to_dataframe()
        query_job=client.query(querys['reviews'])
        res_querys_reviews=query_job.to_dataframe()
        res_query_analisis_sentimientos.drop(columns=['sentiment_label','sentiment'],inplace=True)
    else:
        df_sentiment=[]
        df_reviews=[]
        for a in querys:
            for b in querys[a]:
                if a=='analisis_sentimientos':
                    query_job = client.query(querys['analisis_sentimientos'])
                    res_query_analisis_sentimientos=query_job.to_dataframe()
                    df_sentiment.append(res_query_analisis_sentimientos)
                if a=='reviews':
                    query_job=client.query(querys['reviews'])
                    res_querys_reviews=query_job.to_dataframe()
                    df_reviews.append(res_querys_reviews)
        res_query_analisis_sentimientos=pd.concat(df_sentiment)
        res_query_analisis_sentimientos.drop(columns=['sentiment_label','sentiment'],inplace=True)
        del df_sentiment
        res_querys_reviews=pd.concat(df_reviews)
        del df_reviews
    # Drop rows where 'text' is not a valid string
    res_querys_reviews.dropna(subset=['text'])
    res_querys_reviews= res_querys_reviews[res_querys_reviews['text'].apply(lambda x: isinstance(x, str))]
    filas_procesadas=[]
    for index, row in res_querys_reviews.iterrows():
                is_contained = res_query_analisis_sentimientos[res_query_analisis_sentimientos.eq(row).all(axis=1)].shape[0] > 0
                if is_contained:
                    continue
                else:
                    fila=pd.DataFrame(row).transpose()
                    df=agregar_columnas_sentimientos(fila)
                    writetobigquery(df,'ulta_beauty_sentiment_analysis')
                    filas_procesadas.append(df)
    if len(filas_procesadas)==0:
        return filas_procesadas
    else:
        filas_procesadas=[df for df in filas_procesadas if not df.empty]
        filas_procesadas=pd.concat(filas_procesadas)
        return filas_procesadas
def cargar_logs(df,descripcion,archivo):
    fecha = datetime.now().strftime("%Y-%m-%d")
    hora= datetime.now().strftime("%H:%M:%S")
    lista=[{'Fecha':fecha,'Hora':hora,'Descripción':descripcion,'Archivo':archivo}]
    log=pd.DataFrame(lista)
    df=pd.concat([df,log])
    return df
def upload_to_gcs(bucket_name, file, destination_blob_name):
    # Crea una instancia del cliente de Google Cloud Storage
    client = storage.Client()

    # Obtiene el bucket
    bucket = client.get_bucket(bucket_name)

    # Crea un nuevo blob en el bucket utilizando el nombre de destino proporcionado
    blob = bucket.blob(destination_blob_name)

    # Sube el archivo al blob
    blob.upload_from_file(file)
 

def comprobaciones(filas,logs):
    year_today=datetime.now().year
    year_last_week=(datetime.now()-timedelta(8)).year
    month_last_week=(datetime.now()-timedelta(8)).month
    month_today=datetime.now().month
    if year_today!=year_last_week:
        query_sentiment_analisis_last_year=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.ulta_beauty_sentiment_analysis` where year={year_last_week} and month =12"
        query_sentiment_analisis_current_year=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.ulta_beauty_sentiment_analysis` where year={year_today} and month =1"
        querys=[query_sentiment_analisis_last_year,query_sentiment_analisis_current_year]
    if year_today==year_last_week:
        if month_today!=month_last_week:
            query_sentiment_analisis_last_month=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.ulta_beauty_sentiment_analysis` where year={year_today} and month ={month_last_week}"
            query_sentiment_analisis_current_month=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.ulta_beauty_sentiment_analysis` where year={year_today} and month ={month_today}"
            querys=[query_sentiment_analisis_last_month,query_sentiment_analisis_current_month]
        if month_today==month_last_week:
            query_sentiment_analisis=f"SELECT * FROM `final-project-data-insght-pro.ultabeautyreviews.ulta_beauty_sentiment_analysis` where year={year_today} and month ={month_today}"
            querys=[query_sentiment_analisis]
    df_bigquery=[]
    for comprobacion in querys:
        job=client.query(comprobacion)
        df=job.to_dataframe()
        df_bigquery.append(df)
    df_bigquery=pd.concat(df_bigquery)
    filas_sin_cargar=0
    for index, row in filas.iterrows():
                is_contained = df_bigquery[df_bigquery.eq(row).all(axis=1)].shape[0] > 0
                if is_contained:
                    continue
                else:
                     filas_sin_cargar+=1
    if filas_sin_cargar==0:
         logs=cargar_logs(logs,'filas cargadas correctamante a ulta_beauty_sentiment_analysis','ulta_beauty_sentiment_analysis carga incremental')
         return logs
    else:
        logs=cargar_logs(logs,f'filas pendientes de cargar: {filas_sin_cargar}, checar errores en ulta_beauty_sentiment_analysis','ulta_beauty_sentiment_analysis carga incremental')
        return logs

def run():
    client = storage.Client()
    blob=client.bucket('ultabeauty2024').blob('logs/logs_loads.csv')
    contenido = blob.download_as_text()
    logs=pd.read_csv(StringIO(contenido))
    filas_a_comprobar=[]
    for fuente in ['G','Y']:
        querys=querys_bigquery(fuente)
        filas_procesadas=analisis(querys)
        if len(filas_procesadas)>0:
            filas_a_comprobar.append(filas_procesadas)
    if len(filas_a_comprobar)>0:
        filas_a_comprobar=pd.concat(filas_a_comprobar)
        logs=comprobaciones(filas_a_comprobar,logs)
        csv_content = logs.to_csv(index=False)
# Crear un objeto BytesIO y escribir el contenido CSV
        buffer = io.BytesIO()
        buffer.write(csv_content.encode('utf-8'))
        buffer.seek(0)
# Llama a la función para subir el archivo
        upload_to_gcs('ultabeauty2024',buffer , 'logs/logs_loads.csv')
        return 'reviews actualizadas'
    else:
        logs=cargar_logs(logs,'no hay filas para actualizar','sentiment analisis')
        csv_content = logs.to_csv(index=False)
# Crear un objeto BytesIO y escribir el contenido CSV
        buffer = BytesIO()
        buffer.write(csv_content.encode('utf-8'))
        buffer.seek(0)
# Llama a la función para subir el archivo
        upload_to_gcs('ultabeauty2024',buffer , 'logs/logs_loads.csv')
        return 'reviews actualizadas'