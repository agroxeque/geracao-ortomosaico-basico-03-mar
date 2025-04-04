"""
Módulo de manipuladores para interações com Supabase e WebODM.
Contém funções para manipulação de banco de dados, buckets e processamento de imagens.
"""

import os
import json
import shutil
import requests
import datetime
import traceback
from pyodm import Node
import config
from supabase import create_client, Client

# Inicializa o cliente Supabase
def get_supabase_client() -> Client:
    """Retorna uma instância do cliente Supabase configurado"""
    try:
        return create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    except Exception as e:
        config.logger.error(f"Erro ao criar cliente Supabase: {e}")
        raise

# Funções para manipulação da tabela requisicoes
def criar_registro_requisicao(id_projeto, cliente=None, fazenda=None, talhao=None, data_voo=None, id_talhao=None):
    """
    Cria um registro inicial na tabela requisicoes
    
    Args:
        id_projeto: Identificador do projeto (obrigatório)
        cliente: Nome do cliente (opcional)
        fazenda: Nome da fazenda (opcional)
        talhao: Identificação do talhão (opcional)
        data_voo: Data do voo/levantamento (opcional)
        id_talhao: ID do talhão (opcional)
        
    Returns:
        id: UUID do registro criado
    """
    try:
        config.logger.info(f"Iniciando criação de registro para projeto: {id_projeto}")
        supabase = get_supabase_client()
        
        # Prepara os dados para inserção
        data = {
            "id_projeto": id_projeto,
            "cliente": cliente,
            "fazenda": fazenda,
            "talhao": talhao,
            "data_voo": data_voo,
            "status_orto": "Processando",  # Status inicial
            "id_talhao": id_talhao
        }
        
        # Log detalhado para debug
        config.logger.info(f"Dados a serem inseridos: {data}")
        
        # Insere o registro e retorna os dados
        config.logger.info("Enviando requisição para o Supabase...")
        response = supabase.table("requisicoes").insert(data).execute()
        
        # Log do tipo de resposta e conteúdo
        config.logger.info(f"Tipo de resposta: {type(response)}")
        config.logger.info(f"Resposta completa: {response}")
        
        # Tenta extrair o ID do registro de diferentes maneiras
        try:
            # Primeira tentativa - acesso direto ao dicionário
            if isinstance(response, dict) and "data" in response and len(response["data"]) > 0:
                record_id = response["data"][0]["id"]
                config.logger.info(f"Registro criado com sucesso (método 1). ID: {record_id}")
                return record_id
                
            # Segunda tentativa - acessando a resposta como um objeto
            elif hasattr(response, "data") and response.data and len(response.data) > 0:
                record_id = response.data[0]["id"]
                config.logger.info(f"Registro criado com sucesso (método 2). ID: {record_id}")
                return record_id
                
            # Terceira tentativa - a resposta pode ser uma string representando um JSON
            elif isinstance(response, str):
                import json
                resp_json = json.loads(response)
                if "data" in resp_json and len(resp_json["data"]) > 0:
                    record_id = resp_json["data"][0]["id"]
                    config.logger.info(f"Registro criado com sucesso (método 3). ID: {record_id}")
                    return record_id
            
            # Caso específico para representação string que vimos no teste
            elif str(response).startswith("data=[") and "id" in str(response):
                # Esta é uma solução específica baseada na saída do teste
                import re
                match = re.search(r"'id': '([^']+)'", str(response))
                if match:
                    record_id = match.group(1)
                    config.logger.info(f"Registro criado com sucesso (método 4). ID: {record_id}")
                    return record_id
            
            # Se chegamos aqui, não conseguimos extrair o ID
            config.logger.error(f"Não foi possível extrair o ID do registro: {response}")
            return None
        
        except Exception as e:
            config.logger.error(f"Erro ao extrair ID do registro: {e}")
            return None
            
    except Exception as e:
        config.logger.error(f"Erro ao criar registro na tabela requisicoes: {e}")
        config.logger.error(traceback.format_exc())
        return None
        
def atualizar_registro_requisicao(id_registro, id_wl=None, status_orto=None, url_ortomosaico=None):
    """
    Atualiza um registro existente na tabela requisicoes
    
    Args:
        id_registro: UUID do registro a ser atualizado
        id_wl: ID gerado pelo WebODM (opcional)
        status_orto: Status do processamento (opcional)
        url_ortomosaico: URL do ortomosaico gerado (opcional)
        
    Returns:
        bool: True se atualizado com sucesso, False caso contrário
    """
    try:
        supabase = get_supabase_client()
        
        # Prepara os dados para atualização
        data = {}
        if id_wl is not None:
            data["id_wl"] = id_wl
        if status_orto is not None:
            data["status_orto"] = status_orto
        if url_ortomosaico is not None:
            data["url_ortomosaico"] = url_ortomosaico
            
        # Atualiza o registro
        if data:
            response = supabase.table("requisicoes").update(data).eq("id", id_registro).execute()
            
            config.logger.info(f"Tipo de resposta na atualização: {type(response)}")
            config.logger.info(f"Resposta completa na atualização: {response}")
            
            # Considera atualização bem-sucedida se não houver erro explícito
            return True
        else:
            config.logger.warning("Nenhum dado fornecido para atualização.")
            return False
            
    except Exception as e:
        config.logger.error(f"Erro ao atualizar registro na tabela requisicoes: {e}")
        config.logger.error(traceback.format_exc())
        return False
        
# Funções para manipulação de buckets no Supabase
def baixar_imagens_projeto(id_projeto):
    """
    Baixa as imagens de um projeto do bucket 'uploads'
    
    Args:
        id_projeto: ID do projeto
        
    Returns:
        temp_dir: Diretório onde as imagens foram salvas
        num_imagens: Número de imagens baixadas
    """
    try:
        supabase = get_supabase_client()
        temp_dir = config.get_project_temp_dir(id_projeto)
        
        # Lista os arquivos do projeto no bucket
        response = supabase.storage.from_("uploads").list(id_projeto)
        
        if not response:
            config.logger.error(f"Nenhuma imagem encontrada para o projeto {id_projeto}")
            return temp_dir, 0
            
        config.logger.info(f"Encontradas {len(response)} imagens para o projeto {id_projeto}")
        
        # Filtra por extensões suportadas
        supported_extensions = config.ortomosaico_preset.get("SUPPORTED_IMAGE_EXTENSIONS", 
                                                          ['.jpg', '.jpeg', '.tif', '.tiff', '.png'])
        
        valid_files = [file for file in response 
                      if os.path.splitext(file['name'])[1].lower() in supported_extensions]
        
        config.logger.info(f"{len(valid_files)} imagens com extensões válidas")
        
        # Baixa cada arquivo válido
        contador = 0
        for file in valid_files:
            file_path = f"{id_projeto}/{file['name']}"
            local_path = os.path.join(temp_dir, file['name'])
            
            try:
                # Baixa o arquivo
                file_data = supabase.storage.from_("uploads").download(file_path)
                
                # Salva localmente
                with open(local_path, 'wb') as f:
                    f.write(file_data)
                    
                contador += 1
                if contador % 10 == 0:
                    config.logger.info(f"Baixadas {contador} de {len(valid_files)} imagens...")
                    
            except Exception as e:
                config.logger.error(f"Erro ao baixar arquivo {file_path}: {e}")
        
        config.logger.info(f"Download concluído. {contador} imagens baixadas para {temp_dir}")
        return temp_dir, contador
        
    except Exception as e:
        config.logger.error(f"Erro ao baixar imagens do projeto {id_projeto}: {e}")
        config.logger.error(traceback.format_exc())
        return config.get_project_temp_dir(id_projeto), 0

def enviar_ortomosaico_para_bucket(id_projeto, caminho_ortomosaico):
    """
    Envia o ortomosaico gerado para o bucket 'Ortomosaicos'
    
    Args:
        id_projeto: ID do projeto
        caminho_ortomosaico: Caminho local do arquivo de ortomosaico
        
    Returns:
        url: URL pública do ortomosaico
        success: True se enviado com sucesso, False caso contrário
    """
    try:
        supabase = get_supabase_client()
        
        if not os.path.exists(caminho_ortomosaico):
            config.logger.error(f"Arquivo de ortomosaico não encontrado: {caminho_ortomosaico}")
            return None, False
            
        # Verifica se a pasta existe no bucket, se não, cria
        try:
            supabase.storage.from_("Ortomosaicos").get_public_url(f"{id_projeto}/")
        except:
            # Se der erro, tenta criar a pasta
            try:
                # Cria um arquivo temporário vazio para criar a pasta
                temp_file = os.path.join(config.TEMP_DIR, "temp.txt")
                with open(temp_file, 'w') as f:
                    f.write("")
                
                # Upload do arquivo temporário para criar a pasta
                supabase.storage.from_("Ortomosaicos").upload(
                    f"{id_projeto}/.folder", temp_file
                )
                
                # Remove o arquivo temporário
                os.remove(temp_file)
            except Exception as e:
                config.logger.warning(f"Erro ao criar pasta no bucket: {e}")
                # Continua mesmo se houver erro, pois pode ser que a pasta já exista
        
        # Nome do arquivo no bucket
        nome_arquivo = "odm_ortophoto.tif"
        caminho_bucket = f"{id_projeto}/{nome_arquivo}"
        
        # Faz o upload do arquivo
        with open(caminho_ortomosaico, 'rb') as f:
            supabase.storage.from_("Ortomosaicos").upload(
                caminho_bucket,
                f,
                {"content-type": "image/tiff"}
            )
        
        # Obtém a URL pública
        url = supabase.storage.from_("Ortomosaicos").get_public_url(caminho_bucket)
        
        config.logger.info(f"Ortomosaico enviado com sucesso para o bucket. URL: {url}")
        return url, True
        
    except Exception as e:
        config.logger.error(f"Erro ao enviar ortomosaico para o bucket: {e}")
        config.logger.error(traceback.format_exc())
        return None, False

def enviar_metadados_para_bucket(id_projeto, caminho_metadados):
    """
    Envia o arquivo de metadados para o bucket 'Ortomosaicos'
    
    Args:
        id_projeto: ID do projeto
        caminho_metadados: Caminho local do arquivo de metadados
        
    Returns:
        success: True se enviado com sucesso, False caso contrário
    """
    try:
        supabase = get_supabase_client()
        
        if not os.path.exists(caminho_metadados):
            config.logger.error(f"Arquivo de metadados não encontrado: {caminho_metadados}")
            return False
            
        # Nome do arquivo no bucket deve ser sempre "metadados.txt"
        nome_arquivo = "metadados.txt"
        caminho_bucket = f"{id_projeto}/{nome_arquivo}"
        
        # Faz o upload do arquivo
        with open(caminho_metadados, 'rb') as f:
            supabase.storage.from_("Ortomosaicos").upload(
                caminho_bucket,
                f,
                {"content-type": "text/plain"}
            )
        
        config.logger.info(f"Arquivo de metadados enviado com sucesso para o bucket.")
        return True
        
    except Exception as e:
        config.logger.error(f"Erro ao enviar arquivo de metadados para o bucket: {e}")
        config.logger.error(traceback.format_exc())
        return False

# Funções para processamento de imagens com WebODM
def processar_imagens_webodm(caminho_imagens, id_projeto):
    """
    Processa imagens utilizando WebODM Lightning
    
    Args:
        caminho_imagens: Diretório contendo as imagens
        id_projeto: ID do projeto para identificação
        
    Returns:
        task: Objeto task do WebODM
        success: True se processado com sucesso, False caso contrário
    """
    try:
        config.logger.info(f"Iniciando processamento no WebODM para o projeto {id_projeto}")

        # Conecta ao nó do WebODM
        node = Node(
            config.WEBODM_URL,
            int(config.WEBODM_PORT),
            config.WEBODM_TOKEN
        )
        
        # Lista todas as imagens no diretório
        imagens = []
        for arquivo in os.listdir(caminho_imagens):
            caminho_completo = os.path.join(caminho_imagens, arquivo)
            if os.path.isfile(caminho_completo) and any(arquivo.lower().endswith(ext) for ext in 
                               ['.jpg', '.jpeg', '.tif', '.tiff', '.png']):
                imagens.append(caminho_completo)
        
        if not imagens:
            config.logger.error(f"Nenhuma imagem válida encontrada em {caminho_imagens}")
            return None, False
        
        config.logger.info(f"Processando {len(imagens)} imagens")
        
        # Prepara as opções de processamento usando o preset ativo
        opcoes = config.ortomosaico_preset
        
        # Adiciona opções específicas para este projeto
        opcoes["name"] = f"Projeto_{id_projeto}"
        opcoes["orthophoto-resolution"] = float(opcoes.get("orthophoto-resolution", 5))
        opcoes["dsm"] = opcoes.get("dsm", False)
        opcoes["dtm"] = opcoes.get("dtm", False)
        
        # Força o sistema de coordenadas de saída para WGS84
        opcoes["gcp"] = False
        opcoes["projection"] = "EPSG:4326"
        
        # Cria a tarefa no WebODM
        task = node.create_task(
            imagens,
            opcoes,
            progress_callback=lambda progress: config.logger.info(f"Progresso: {progress}%")
        )
        
        config.logger.info(f"Tarefa criada no WebODM. ID: {task.uuid}")
        return task, True
        
    except Exception as e:
        config.logger.error(f"Erro ao processar imagens no WebODM: {e}")
        config.logger.error(traceback.format_exc())
        return None, False

def aguardar_processamento(task):
    """
    Aguarda a conclusão do processamento no WebODM
    
    Args:
        task: Objeto task do WebODM
        
    Returns:
        status: Status final da tarefa
        success: True se concluído com sucesso, False caso contrário
    """
    try:
        config.logger.info("Aguardando conclusão do processamento...")
        
        # Configura o tempo máximo de espera (18 horas = 64800 segundos)
        max_timeout = 64800
        
        # Aguarda a conclusão da tarefa
        task.wait_for_completion(
            interval=30,  # Verifica a cada 30 segundos
            max_retries=max_timeout//30,
            retry_timeout=5
        )
        
        # Obtém informações atualizadas da tarefa
        info = task.info()
        status = info.status.name
        
        config.logger.info(f"Processamento concluído com status: {status}")
        return status, status == "COMPLETED"
        
    except Exception as e:
        config.logger.error(f"Erro ao aguardar processamento: {e}")
        config.logger.error(traceback.format_exc())
        return "FAILED", False

def baixar_resultados(task, id_projeto):
    """
    Baixa os resultados do processamento do WebODM
    
    Args:
        task: Objeto task do WebODM
        id_projeto: ID do projeto
        
    Returns:
        caminho_ortomosaico: Caminho para o arquivo de ortomosaico
        success: True se baixado com sucesso, False caso contrário
    """
    try:
        config.logger.info("Baixando resultados do processamento...")
        
        # Diretório para os resultados
        dir_resultados = os.path.join(config.get_project_temp_dir(id_projeto), "resultados")
        os.makedirs(dir_resultados, exist_ok=True)
        
        # Baixa os assets
        caminho_assets = task.download_assets(dir_resultados)
        
        # Verifica se o ortomosaico foi gerado
        caminho_ortomosaico_original = os.path.join(dir_resultados, "odm_orthophoto", "odm_orthophoto.tif")
        
        if not os.path.exists(caminho_ortomosaico_original):
            config.logger.error(f"Ortomosaico não encontrado em {caminho_ortomosaico_original}")
            return None, False
            
        # Define o caminho final para o ortomosaico
        caminho_ortomosaico_final = os.path.join(dir_resultados, "odm_orthophoto.tif")
        
        # Copia o arquivo para o diretório de resultados com o nome padrão
        shutil.copy2(caminho_ortomosaico_original, caminho_ortomosaico_final)
        
        config.logger.info(f"Ortomosaico baixado com sucesso: {caminho_ortomosaico_final}")
        return caminho_ortomosaico_final, True
        
    except Exception as e:
        config.logger.error(f"Erro ao baixar resultados: {e}")
        config.logger.error(traceback.format_exc())
        return None, False
        
# Funções para geração de metadados
def gerar_metadados(id_projeto, dir_imagens, caminho_ortomosaico, task, opcoes, num_imagens, dados_requisicao=None):
    """
    Gera arquivo de metadados para o ortomosaico conforme o modelo padrão
    
    Args:
        id_projeto: ID do projeto
        dir_imagens: Diretório das imagens
        caminho_ortomosaico: Caminho do ortomosaico
        task: Objeto task do WebODM
        opcoes: Opções de processamento utilizadas
        num_imagens: Número de imagens processadas
        dados_requisicao: Dados adicionais da requisição (cliente, fazenda, etc.)
        
    Returns:
        caminho_metadados: Caminho do arquivo de metadados
    """
    try:
        config.logger.info(f"Gerando metadados para o projeto {id_projeto}")
        
        # Diretório para o arquivo de metadados
        dir_resultados = os.path.dirname(caminho_ortomosaico)
        
        # Coleta informações da tarefa
        info = task.info()
        
        # Obtém data e hora atual no formato brasileiro
        agora = datetime.datetime.now(config.timezone)
        data_hora = agora.strftime("%Y-%m-%d %H:%M:%S %z")
        
        # Extrai dados adicionais da requisição
        dados_adicionais = dados_requisicao or {}
        cliente = dados_adicionais.get('cliente', '')
        fazenda = dados_adicionais.get('fazenda', '')
        talhao = dados_adicionais.get('talhao', '')
        data_levantamento = dados_adicionais.get('data_voo', '')
        
        # Obtém informações de preset
        preset_nome = config.ACTIVE_PRESET
        
        # Obtém informações do sistema
        import platform
        import sys
        import socket
        
        # Cria arquivo de metadados em formato texto
        caminho_metadados = os.path.join(dir_resultados, "metadados.txt")
        with open(caminho_metadados, 'w', encoding='utf-8') as f:
            f.write("METADADOS DO ORTOMOSAICO\n")
            f.write("========================\n\n")
            
            f.write(f"ID do Projeto: {id_projeto}\n")
            f.write(f"Data de Processamento: {data_hora}\n\n")
            
            f.write("INFORMAÇÕES ADICIONAIS\n")
            f.write("----------------------\n")
            if cliente:
                f.write(f"cliente: {cliente}\n")
            if fazenda:
                f.write(f"fazenda: {fazenda}\n")
            if talhao:
                f.write(f"talhao: {talhao}\n")
            if data_levantamento:
                f.write(f"data_levantamento: {data_levantamento}\n")
            f.write("\n")
            
            f.write("INFORMAÇÕES DE PROCESSAMENTO\n")
            f.write("----------------------------\n")
            f.write(f"Preset Utilizado: {preset_nome}\n")
            f.write(f"Quantidade de Imagens: {num_imagens}\n")
            
            # Tempo de processamento
            if info.processing_time:
                tempo_proc = info.processing_time / 1000  # Converter para segundos
                f.write(f"Tempo de Processamento: {tempo_proc} segundos\n")
                
            f.write(f"Task ID: {task.uuid}\n")
            f.write(f"Status: {info.status.name.lower()}\n\n")
            
            f.write("PARÂMETROS DE PROCESSAMENTO\n")
            f.write("----------------------------\n")
            
            # Escreve os parâmetros mais relevantes de processamento
            for param, valor in sorted(opcoes.items()):
                # Filtra para parâmetros que devem aparecer no relatório
                if isinstance(valor, (str, int, float, bool)) and not param.startswith('_'):
                    f.write(f"{param}: {valor}\n")
            
            # Adiciona a projeção explicitamente
            f.write("proj: EPSG:4326\n\n")
            
            f.write("INFORMAÇÕES DO ORTOMOSAICO\n")
            f.write("---------------------------\n")
            f.write("Sistema de Coordenadas: EPSG:4326\n")
            f.write("Nome do Arquivo: odm_orthophoto.tif\n\n")
            
            f.write("INFORMAÇÕES DO SISTEMA\n")
            f.write("----------------------\n")
            f.write(f"host: {socket.gethostname()}\n")
            f.write(f"system: {platform.system()}\n")
            f.write(f"python_version: {sys.version.split()[0]}\n")
            f.write(f"timezone: {config.TIMEZONE}\n")
        
        config.logger.info(f"Metadados gerados com sucesso: {caminho_metadados}")
        return caminho_metadados
        
    except Exception as e:
        config.logger.error(f"Erro ao gerar metadados: {e}")
        config.logger.error(traceback.format_exc())
        return None
        
# Funções para notificação via webhook
def enviar_webhook(id_projeto, status, url_ortomosaico=None, mensagem=None):
    """
    Envia notificação via webhook
    
    Args:
        id_projeto: ID do projeto
        status: Status do processamento
        url_ortomosaico: URL do ortomosaico (opcional)
        mensagem: Mensagem adicional (opcional)
        
    Returns:
        success: True se enviado com sucesso, False caso contrário
    """
    try:
        if not config.WEBHOOK_URL:
            config.logger.warning("URL de webhook não configurada. Notificação não enviada.")
            return False
            
        config.logger.info(f"Enviando notificação via webhook para o projeto {id_projeto}")
        
        # Prepara payload para o webhook
        payload = {
            "id_projeto": id_projeto,
            "status": status,
            "timestamp": datetime.datetime.now(config.timezone).isoformat()
        }
        
        # Se a URL do ortomosaico não foi fornecida e o status é sucesso, tenta obtê-la do banco
        if status == "sucesso" and not url_ortomosaico:
            try:
                supabase = get_supabase_client()
                response = supabase.table("requisicoes").select("url_ortomosaico").eq("id_projeto", id_projeto).execute()
                
                if "data" in response and len(response["data"]) > 0 and response["data"][0].get("url_ortomosaico"):
                    url_ortomosaico = response["data"][0]["url_ortomosaico"]
                    config.logger.info(f"URL do ortomosaico obtida do banco: {url_ortomosaico}")
            except Exception as e:
                config.logger.warning(f"Não foi possível obter URL do ortomosaico do banco: {e}")
        
        # Inclui URL do ortomosaico no payload se disponível
        if url_ortomosaico:
            payload["url_ortomosaico"] = url_ortomosaico
            
        if mensagem:
            payload["mensagem"] = mensagem
        
        # Envia requisição para o webhook
        headers = {'Content-Type': 'application/json'}
        config.logger.info(f"Enviando webhook com payload: {payload}")
        
        response = requests.post(
            config.WEBHOOK_URL,
            data=json.dumps(payload),
            headers=headers
        )
        
        if response.status_code >= 200 and response.status_code < 300:
            config.logger.info(f"Webhook enviado com sucesso. Status: {response.status_code}")
            return True
        else:
            config.logger.error(f"Erro ao enviar webhook. Status: {response.status_code}, Resposta: {response.text}")
            return False
            
    except Exception as e:
        config.logger.error(f"Erro ao enviar webhook: {e}")
        config.logger.error(traceback.format_exc())
        return False
        
# Funções de limpeza
def limpar_arquivos_temporarios(id_projeto):
    """
    Remove os arquivos temporários do projeto
    
    Args:
        id_projeto: ID do projeto
        
    Returns:
        success: True se removido com sucesso, False caso contrário
    """
    try:
        dir_projeto = config.get_project_temp_dir(id_projeto)
        
        if os.path.exists(dir_projeto):
            config.logger.info(f"Removendo arquivos temporários do projeto {id_projeto}")
            shutil.rmtree(dir_projeto)
            config.logger.info(f"Arquivos temporários removidos com sucesso")
            return True
        else:
            config.logger.warning(f"Diretório temporário não encontrado: {dir_projeto}")
            return False
            
    except Exception as e:
        config.logger.error(f"Erro ao remover arquivos temporários: {e}")
        config.logger.error(traceback.format_exc())
        return False

# Verificação básica de funcionamento, se executado diretamente
if __name__ == "__main__":
    config.logger.info("Testando módulo de handlers")
    try:
        supabase = get_supabase_client()
        config.logger.info("Conexão com Supabase estabelecida com sucesso")
           
        # Testando conexão com WebODM
        try:
            node = Node(
                config.WEBODM_URL,
                int(config.WEBODM_PORT),
                config.WEBODM_TOKEN
            )
            node_info = node.info()
            config.logger.info(f"Conexão com WebODM estabelecida com sucesso. Versão: {node_info.version}")
        except Exception as e:
            config.logger.error(f"Erro ao conectar com WebODM: {e}")
    except Exception as e:
        config.logger.error(f"Erro ao conectar com Supabase: {e}")
