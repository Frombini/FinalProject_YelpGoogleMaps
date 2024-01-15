FROM python:3.11.6

# Instalar las bibliotecas necesarias
RUN pip install google-cloud-bigquery
RUN pip install pandas
RUN pip install pyarrow
RUN pip install apache-beam==2.43.0
RUN pip install geopy
RUN pip install google-cloud-bigquery
RUN pip install polars
RUN pip install apache-beam[gcp]
RUN pip install google-cloud-storage

# Copiar tu script al contenedor
COPY pipeline_apache_beam.py /dataflow/
COPY windy-tiger-410421-956bf231305a.json /dataflow/

# Definir el directorio de trabajo
WORKDIR /dataflow/

# Establecer el comando predeterminado para abrir una terminal interactiva
CMD ["/bin/bash"]