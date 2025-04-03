"""
Configurações e parâmetros para o sistema de processamento de ortomosaicos.
Este arquivo centraliza todos os parâmetros configuráveis do sistema.
"""

#exemplo de comopoderia ser criado o arquivo que forcenerá os parâmetros de geração do Ortomosaico, no âmbito do sistema PyODM


# Presets de qualidade para processamento ODM
# Todos os parâmetros estão documentados em: https://docs.opendronemap.org/arguments/
ODM_QUALITY_PRESETS = {
    # Preset padrão - equilibra qualidade e robustez
    "padrao": {
        "feature-quality": "high",
        "min-num-features": 10000,
        "matcher-neighbors": 8,
        "matcher-distance": 3,
        "feature-type": "sift",
        "optimize-disk-space": True,
        "pc-quality": "high",
        "pc-filter": 2.5,
        "depthmap-resolution": 640,
        "dem-resolution": "2",
        "orthophoto-cutline": True,
        "use-3dmesh": True,
        "cog": True,
        "auto-boundary": True,
        "dsm": False,             # Desabilitar DSM (não necessário)
        "dtm": False,             # Desabilitar DTM (não necessário)
        "skip-3dmodel": True,     # Pular modelo 3D para economizar tempo
        "skip-report": True,      # Pular relatório para economizar tempo
        "pc-classify": False      # Desabilitar classificação de nuvem de pontos
    },
    
    # Alta qualidade - prioriza qualidade sobre velocidade
    "alta": {
        "feature-quality": "high",
        "min-num-features": 16000,
        "matcher-neighbors": 10,
        "matcher-distance": 3,
        "feature-type": "sift",
        "optimize-disk-space": False,
        "pc-quality": "high",
        "pc-filter": 2.5,
        "depthmap-resolution": 1024,
        "dem-resolution": "1",
        "orthophoto-cutline": True,
        "use-3dmesh": True,
        "cog": True,
        "auto-boundary": True,
        "dsm": False,
        "dtm": False,
        "skip-3dmodel": True,
        "skip-report": True,
        "pc-classify": False
    },
    
    # Robusta - prioriza completude sobre precisão
    "robusta": {
        "feature-quality": "high",
        "min-num-features": 8000,
        "matcher-neighbors": 12,
        "matcher-distance": 5,    # Maior distância de busca para imagens de baixa qualidade
        "feature-type": "sift",
        "optimize-disk-space": True,
        "pc-quality": "high",
        "pc-filter": 3.0,         # Mais tolerante a outliers
        "depthmap-resolution": 512,
        "dem-resolution": "2",
        "orthophoto-cutline": True,
        "use-3dmesh": True,
        "cog": True,
        "auto-boundary": True,
        "dsm": False,
        "dtm": False,
        "skip-3dmodel": True,
        "skip-report": True,
        "force-gps": True,        # Força o uso de coordenadas GPS
        "gps-accuracy": 10,       # Maior tolerância para erros de GPS
        "pc-classify": False
    },
    
    # Rápida - prioriza velocidade sobre qualidade
    "rapida": {
        "feature-quality": "medium",
        "min-num-features": 6000,
        "matcher-neighbors": 6,
        "feature-type": "sift",
        "optimize-disk-space": True,
        "pc-quality": "medium",
        "pc-filter": 2.5,
        "depthmap-resolution": 384,
        "dem-resolution": "5",
        "orthophoto-cutline": True,
        "use-3dmesh": True,
        "cog": True,
        "auto-boundary": True,
        "dsm": False,
        "dtm": False,
        "skip-3dmodel": True,
        "skip-report": True,
        "pc-classify": False
    }
}

# Preset ativo - pode ser alterado conforme necessário
ACTIVE_PRESET = "padrao"

# Configurações de download de imagens
DOWNLOAD_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB por chunk
MAX_CONCURRENT_DOWNLOADS = 5

# Configurações de upload
UPLOAD_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB por chunk
MAX_CONCURRENT_UPLOADS = 3

# Configurações de processamento
MAX_RETRIES = 3
RETRY_DELAY = 5  # segundos entre tentativas

# Configurações de monitoramento
POLLING_INTERVAL = 30  # segundos entre verificações de status

# Configurações de timeout (segundos)
# Estas podem ser sobrescritas pelas configurações no .env
DEFAULT_BASE_TIMEOUT = 300
DEFAULT_TIMEOUT_PER_IMAGE = 120
DEFAULT_MAX_TIMEOUT = 64800  # 18 horas

# Sistema de coordenadas de saída
OUTPUT_CRS = "EPSG:4326"  # WGS84

# Tipos de arquivos suportados (extensões)
SUPPORTED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.tif', '.tiff', '.png']

# Formato do nome do arquivo de saída
OUTPUT_FILENAME = "odm_orthophoto.tif"
METADATA_JSON_FILENAME = "odm_orthophoto_metadata.json"
METADATA_TXT_FILENAME = "odm_orthophoto_metadata.txt"
