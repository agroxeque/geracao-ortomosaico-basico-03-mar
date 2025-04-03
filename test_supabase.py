import os
import traceback
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega variáveis de ambiente
load_dotenv()

# Configurações do Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

print(f"Testando conexão com Supabase")
print(f"URL: {SUPABASE_URL[:20]}..." if SUPABASE_URL else "URL não encontrada")
print(f"KEY: {SUPABASE_KEY[:5]}..." if SUPABASE_KEY else "KEY não encontrada")

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Cliente Supabase criado com sucesso")
    
    # Tenta verificar a existência da tabela requisicoes
    response = supabase.table("requisicoes").select("id").limit(1).execute()
    print(f"Consulta básica executada com sucesso: {response}")
    
    # Tenta inserir um registro de teste
    test_data = {
        "id_projeto": "teste_script",
        "cliente": "Cliente de teste",
        "status_orto": "Teste"
    }
    
    print(f"Tentando inserir dados de teste: {test_data}")
    response = supabase.table("requisicoes").insert(test_data).execute()
    print(f"Inserção de teste resultou em: {response}")
    
    if "data" in response and len(response["data"]) > 0:
        print("✅ Teste de inserção bem-sucedido!")
        
        # Remover o registro de teste
        record_id = response["data"][0]["id"]
        supabase.table("requisicoes").delete().eq("id", record_id).execute()
        print(f"Registro de teste removido")
    else:
        print("❌ Teste de inserção falhou")
        if "error" in response:
            print(f"Erro: {response['error']}")
            
except Exception as e:
    print(f"❌ Erro durante o teste: {e}")
    print(traceback.format_exc())
