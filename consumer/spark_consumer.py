from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, when
from pyspark.sql.types import StructType, StringType, IntegerType

spark = (
    SparkSession.builder
    .appName("ClientTicketsToParquet")
    .config("spark.sql.shuffle.partitions", "4") # Nombre de partitions
    .getOrCreate() # Récupère ou créé la session
)
spark.sparkContext.setLogLevel("WARN") # Logs minimums

schema = ( # Définition du schéma de données attendu
    StructType()
    .add("ticket_id", StringType())
    .add("client_id", IntegerType())
    .add("created_at", StringType())
    .add("demande", StringType())
    .add("type_demande", StringType())
    .add("priorite", StringType())
)

raw_df = (
    spark.readStream.format("kafka") # Lecture en streaming au format kafka/redpanda
    .option("kafka.bootstrap.servers", "redpanda:9092") # Adresse du broker
    .option("subscribe", "client-tickets")
    .option("startingOffsets", "earliest") # Reprends le stream au offset le plus tôt
    .option("failOnDataLoss", "false") # Saute les offset manquant en cas de redémarrage du container: incohérence offset/checkpoint 
    .load()
)

tickets_df = raw_df.select(
    from_json(col("value").cast("string"), schema).alias("data") # Récupère la valeur du stream en bytes, le cast en json, puis le parse selon le schema défini
).select("data.*")

enriched_df = tickets_df.withColumn( # Ajoute une nouvelle colonne selon le type de demande
    "support_team",
    when(col("type_demande") == "incident", "Team A")
    .when(col("type_demande") == "facturation", "Team B")
    .when(col("type_demande") == "technique", "Team C")
    .otherwise("Team D")
)

query = (
    enriched_df.writeStream # Ecrit le stream au format parquet
    .format("parquet")
    .outputMode("append")
    .partitionBy("type_demande") # Partition pruning, permet d'optimiser la lecture sur les requêtes impliquant le type de demande
    .option("path", "/data/parquet/client-tickets")
    .option("checkpointLocation", "/data/checkpoints/client-tickets")
    .trigger(processingTime="30 seconds") # Traitements des events kafka par microbatch ( temps élevé pour éviter trop de petits fichiers)
    .start()
)

query.awaitTermination() # Bloque le programme et laisse tourner le stream jusqu'a arrêt forcé du programme