"""
API de Processamento de Ortomosaicos

Implementa uma API para processamento de imagens de drone usando WebODM Lightning,
com armazenamento em Supabase.
"""

import os
import time
import traceback
import threading
from flask import Flask, request, jsonify
from functools import wraps

import config
import handlers

# Inicialização do aplicativo Flask
app = Flask(__name__)

# Middleware para autenticação da API
def require_apikey(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key and api_key == config.API_KEY:
            return view_function(*args, **kwargs)
        else:
            return jsonify({"erro": "Acesso não autorizado"}), 401
    return decorated_function

# Rota de status da API
@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        "status": "online",
        "versao": "1.0.0",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    })

# Rota principal para processamento de ortomosaicos
@app.route('/processar', methods=['POST'])
@require_apikey
def processar_ortomosaico():
    try:
        # Extrai os dados da requisição
        dados = request.json
        
        # Valida os dados recebidos
        if not dados:
            return jsonify({"erro": "Nenhum dado recebido"}), 400
        
        if 'id_projeto' not in dados:
            return jsonify({"erro": "Campo obrigatório 'id_projeto' não encontrado"}), 400
        
        id_projeto = dados['id_projeto']
        cliente = dados.get('cliente')
        fazenda = dados.get('fazenda')
        talhao = dados.get('talhao')
        data_voo = dados.get('data_levantamento')  # Nota: campo renomeado conforme requisitos
        
        config.logger.info(f"Iniciando processamento do projeto {id_projeto}")
        
        # Cria registro na tabela requisicoes
        registro_id = handlers.criar_registro_requisicao(
            id_projeto, cliente, fazenda, talhao, data_voo
        )
        
        if not registro_id:
            return jsonify({"erro": "Falha ao criar registro na tabela de requisições"}), 500
        
        config.logger.info(f"Registro criado na tabela requisicoes: {registro_id}")
        
        # Inicia o processamento em uma thread separada
        thread = threading.Thread(
            target=processar_projeto,
            args=(id_projeto, registro_id, dados)
        )
        thread.daemon = True  # Thread finaliza quando o programa principal terminar
        thread.start()
        
        # Responde imediatamente, não esperando o processamento
        return jsonify({
            "mensagem": "Processamento iniciado com sucesso",
            "id_registro": registro_id,
            "id_projeto": id_projeto,
            "status": "Em processamento"
        }), 202
        
    except Exception as e:
        config.logger.error(f"Erro ao processar requisição: {e}")
        config.logger.error(traceback.format_exc())
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

def processar_projeto(id_projeto, registro_id, dados_requisicao=None):
    """
    Processa um projeto completo
    
    Args:
        id_projeto: ID do projeto
        registro_id: ID do registro na tabela requisicoes
        dados_requisicao: Dados originais da requisição
    """
    try:
        # 1. Baixar imagens do bucket
        dir_imagens, num_imagens = handlers.baixar_imagens_projeto(id_projeto)
        
        if num_imagens == 0:
            config.logger.error(f"Nenhuma imagem encontrada para o projeto {id_projeto}")
            handlers.atualizar_registro_requisicao(registro_id, status_orto="Erro: Nenhuma imagem encontrada")
            handlers.enviar_webhook(id_projeto, "erro", mensagem="Nenhuma imagem encontrada")
            return False
        
        # 2. Processar imagens no WebODM
        task, success = handlers.processar_imagens_webodm(dir_imagens, id_projeto)
        
        if not success or task is None:
            config.logger.error(f"Falha ao iniciar processamento no WebODM para o projeto {id_projeto}")
            handlers.atualizar_registro_requisicao(registro_id, status_orto="Erro: Falha ao iniciar processamento")
            handlers.enviar_webhook(id_projeto, "erro", mensagem="Falha ao iniciar processamento no WebODM")
            handlers.limpar_arquivos_temporarios(id_projeto)
            return False
        
        # Atualiza o registro com o ID da tarefa do WebODM
        handlers.atualizar_registro_requisicao(registro_id, id_wl=task.uuid)
        
        # 3. Aguardar a conclusão do processamento
        status, success = handlers.aguardar_processamento(task)
        
        if not success:
            config.logger.error(f"Processamento falhou para o projeto {id_projeto}. Status: {status}")
            handlers.atualizar_registro_requisicao(registro_id, status_orto=f"Erro: {status}")
            handlers.enviar_webhook(id_projeto, "erro", mensagem=f"Processamento falhou: {status}")
            handlers.limpar_arquivos_temporarios(id_projeto)
            return False
        
        # 4. Baixar resultados
        caminho_ortomosaico, success = handlers.baixar_resultados(task, id_projeto)
        
        if not success or not caminho_ortomosaico:
            config.logger.error(f"Falha ao baixar resultados para o projeto {id_projeto}")
            handlers.atualizar_registro_requisicao(registro_id, status_orto="Erro: Falha ao baixar resultados")
            handlers.enviar_webhook(id_projeto, "erro", mensagem="Falha ao baixar resultados")
            handlers.limpar_arquivos_temporarios(id_projeto)
            return False
        
        # 5. Gerar apenas o arquivo de metadados TXT
        caminho_metadados = handlers.gerar_metadados(
            id_projeto, dir_imagens, caminho_ortomosaico, task, 
            config.ortomosaico_preset, num_imagens, dados_requisicao
        )
        
        if not caminho_metadados:
            config.logger.warning(f"Falha ao gerar metadados para o projeto {id_projeto}")
            # Continua o processamento mesmo sem os metadados
        
        # 6. Enviar ortomosaico para o bucket
        url_ortomosaico, success = handlers.enviar_ortomosaico_para_bucket(id_projeto, caminho_ortomosaico)
        
        if not success or not url_ortomosaico:
            config.logger.error(f"Falha ao enviar ortomosaico para o bucket para o projeto {id_projeto}")
            handlers.atualizar_registro_requisicao(registro_id, status_orto="Erro: Falha ao enviar ortomosaico")
            handlers.enviar_webhook(id_projeto, "erro", mensagem="Falha ao enviar ortomosaico para o bucket")
            handlers.limpar_arquivos_temporarios(id_projeto)
            return False
        
        # 7. Enviar metadados para o bucket (apenas o TXT)
        if caminho_metadados:
            handlers.enviar_metadados_para_bucket(id_projeto, caminho_metadados)
        
        # 8. Atualizar registro na tabela requisicoes com a URL do ortomosaico
        success_db = handlers.atualizar_registro_requisicao(
            registro_id, status_orto="Sucesso", url_ortomosaico=url_ortomosaico
        )
        
        if not success_db:
            config.logger.error(f"Falha ao atualizar registro na tabela para o projeto {id_projeto}")
            handlers.enviar_webhook(id_projeto, "erro", mensagem="Falha ao atualizar registro no banco de dados")
            handlers.limpar_arquivos_temporarios(id_projeto)
            return False
            
        # 9. Enviar webhook de sucesso APENAS APÓS atualização da tabela
        handlers.enviar_webhook(id_projeto, "sucesso", url_ortomosaico=url_ortomosaico)
        
        # 10. Limpar arquivos temporários
        handlers.limpar_arquivos_temporarios(id_projeto)
        
        config.logger.info(f"Processamento concluído com sucesso para o projeto {id_projeto}")
        return True
        
    except Exception as e:
        config.logger.error(f"Erro durante o processamento do projeto {id_projeto}: {e}")
        config.logger.error(traceback.format_exc())
        
        # Atualiza o registro com o erro
        handlers.atualizar_registro_requisicao(registro_id, status_orto=f"Erro: {str(e)}")
        
        # Envia webhook de erro
        handlers.enviar_webhook(id_projeto, "erro", mensagem=str(e))
        
        # Limpa arquivos temporários
        handlers.limpar_arquivos_temporarios(id_projeto)
        
        return False

# Inicia o servidor Flask quando executado diretamente
if __name__ == "__main__":
    if not config.config_valid:
        config.logger.error("Configurações inválidas. Verifique o arquivo .env")
        exit(1)
    
    # Cria diretórios necessários
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    
    # Inicia o servidor
    host = config.HOST_IP or "0.0.0.0"
    port = 5000
    
    config.logger.info(f"Iniciando servidor na porta {port}")
    app.run(host=host, port=port, debug=False)
