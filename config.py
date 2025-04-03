"""
Módulo de configuração para o sistema de geração de ortomosaicos.
Responsável por carregar configurações do arquivo .env e presets de qualidade do settings.py.
"""

import os
import logging
import datetime
import pytz
from dotenv import load_dotenv
from settings import ODM_QUALITY_PRESETS

# Configuração de logging
def setup_logging():
    """Configura o sistema de logging"""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(log_dir, f'ortomosaico_{timestamp}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()
logger = setup_logging()

# Configurações do servidor
HOST_IP = os.getenv('HOST_IP')
TIMEZONE = os.getenv('TIMEZONE', 'America/Sao_Paulo')

# Configurações do Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Configurações do WebODM
WEBODM_URL = os.getenv('WEBODM_URL')
WEBODM_PORT = os.getenv('WEBODM_PORT')
WEBODM_TOKEN = os.getenv('WEBODM_TOKEN')

# Configuração de qualidade do ortomosaico
ACTIVE_PRESET = os.getenv('ACTIVE_PRESET', 'padrao')

# URL para webhook
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# API Key para autenticação
API_KEY = os.getenv('API_KEY')

# Configurações de diretórios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, 'temp')

def get_active_preset():
    """Retorna o preset ativo de configurações de qualidade do ODM"""
    if ACTIVE_PRESET not in ODM_QUALITY_PRESETS:
        logger.warning(f"Preset '{ACTIVE_PRESET}' não encontrado. Usando 'padrao'.")
        return ODM_QUALITY_PRESETS['padrao']
    
    logger.info(f"Usando preset de qualidade: {ACTIVE_PRESET}")
    return ODM_QUALITY_PRESETS[ACTIVE_PRESET]

def get_timezone():
    """Retorna o objeto timezone configurado"""
    try:
        return pytz.timezone(TIMEZONE)
    except Exception as e:
        logger.error(f"Erro ao configurar timezone {TIMEZONE}: {e}")
        logger.info("Usando UTC como fallback")
        return pytz.UTC

def validate_config():
    """Valida se todas as configurações necessárias estão presentes"""
    required_vars = [
        ('SUPABASE_URL', SUPABASE_URL),
        ('SUPABASE_KEY', SUPABASE_KEY),
        ('WEBODM_URL', WEBODM_URL),
        ('WEBODM_PORT', WEBODM_PORT),
        ('WEBODM_TOKEN', WEBODM_TOKEN),
        ('API_KEY', API_KEY),
        ('WEBHOOK_URL', WEBHOOK_URL)
    ]
    
    missing = [name for name, value in required_vars if not value]
    
    if missing:
        logger.error(f"Variáveis de ambiente obrigatórias não encontradas: {', '.join(missing)}")
        return False
    
    logger.info("Todas as configurações necessárias estão presentes.")
    return True

def get_project_temp_dir(id_projeto):
    """Retorna o diretório temporário para um projeto específico"""
    project_dir = os.path.join(TEMP_DIR, id_projeto)
    os.makedirs(project_dir, exist_ok=True)
    return project_dir

# Inicialização
timezone = get_timezone()
ortomosaico_preset = get_active_preset()

# Verifica configurações
config_valid = validate_config()
if not config_valid:
    logger.warning("Sistema pode não funcionar corretamente devido a configurações ausentes.")

if __name__ == "__main__":
    # Teste simples se este arquivo for executado diretamente
    logger.info("Testando módulo de configuração")
    logger.info(f"Preset ativo: {ACTIVE_PRESET}")
    logger.info(f"Configurações do preset: {ortomosaico_preset}")
    logger.info(f"Timezone: {timezone}")
    logger.info(f"Diretório base: {BASE_DIR}")
    logger.info(f"Diretório temp: {TEMP_DIR}")
