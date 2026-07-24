from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    VECTORS_ROOT: str = "./data/vectors"
    CLUSTERS_ROOT: str = "./data/clusters"
    UMAP_N_COMPONENTS: int = 5
    HDBSCAN_MIN_CLUSTER_SIZE: int = 5
    PORT: int = 8004

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()