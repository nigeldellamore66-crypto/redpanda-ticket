from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count

spark = (
    SparkSession.builder
    .appName("ClientTicketsBatchAgg")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

# Lit les Parquet produits par le job streaming
df = spark.read.parquet("/data/parquet/client-tickets")

# Agrégation : nb de tickets par type
agg = (
    df.groupBy("type_demande")
      .agg(count("*").alias("nb_tickets"))
      .orderBy(col("nb_tickets").desc())
)

# Export du résultat
agg.write.mode("overwrite").parquet("/data/reports/tickets_by_type")

# Affichage logs
agg.show(truncate=False)

spark.stop()