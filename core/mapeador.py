import os
from selenium.webdriver.common.by import By
from core.logger import get_logger

logger = get_logger("MAPEADOR")

def mapear_campos(driver, nome_arquivo="mapa_universal.txt"):
    """
    VARREDURA COMPLETA: Percorre recursivamente TODOS os frames e iframes
    da janela atual e salva todos os inputs/botões em um arquivo texto.
    """
    logger.info(f"--- INICIANDO MAPEAMENTO UNIVERSAL ({nome_arquivo}) ---")
    
    # Garante início do topo
    driver.switch_to.default_content()
    
    path_absoluto = os.path.abspath(nome_arquivo)
    
    try:
        with open(path_absoluto, "w", encoding="utf-8") as f:
            titulo = driver.title or "Sem Titulo"
            f.write(f"=== MAPA GERADO EM: {titulo} ===\n")
            f.write(f"URL: {driver.current_url}\n\n")
            
            # Inicia recursão
            _explorar_frames_recursivo(driver, f, "ROOT")
            
        logger.info(f"Mapeamento concluído. Salvo em: {path_absoluto}")
    except Exception as e:
        logger.error(f"Erro fatal durante mapeamento: {e}")
    finally:
        # Sempre volta para o topo ao final
        driver.switch_to.default_content()

def _explorar_frames_recursivo(driver, arquivo, hierarquia_atual):
    """
    Função interna recursiva.
    """
    # 1. Identificação
    try:
        nome_frame = driver.execute_script("return window.name") or "(sem nome)"
    except:
        nome_frame = "Erro ao ler nome"

    logger.debug(f"Varrendo: {hierarquia_atual} [{nome_frame}]")
    arquivo.write(f"\n{'='*60}\n")
    arquivo.write(f"CONTEXTO: {hierarquia_atual} | NOME: {nome_frame}\n")
    arquivo.write(f"{'='*60}\n")

    # 2. Extração (Jurassic JS)
    js_jurassic = """
    var itens = [];
    var tags = ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON', 'A', 'IMG'];
    
    for (var t = 0; t < tags.length; t++) {
        var elementos = document.getElementsByTagName(tags[t]);
        for (var i = 0; i < elementos.length; i++) {
            var e = elementos[i];
            
            // Filtro para links vazios
            if (tags[t] == 'A' && (!e.innerText || e.innerText.replace(/^\\s+|\\s+$/g, '') == '')) continue;
            
            var txt = e.innerText || '';
            var src = e.getAttribute('src') || '';
            
            itens.push({
                tag: tags[t],
                id: e.id || '',
                name: e.name || '',
                type: e.getAttribute('type') || '',
                val: e.value || '',
                txt: txt.replace(/\\n/g, ' ').substring(0, 50),
                click: e.getAttribute('onclick') || '',
                src: src.split('/').pop() // Só o nome do arquivo
            });
        }
    }
    return itens;
    """
    
    try:
        dados = driver.execute_script(js_jurassic)
        
        if dados:
            for d in dados:
                linha = (f"TAG: {d['tag']:<7} | "
                         f"ID: {d['id']:<15} | "
                         f"NAME: {d['name']:<20} | "
                         f"VAL: {d['val']:<15} | "
                         f"TXT: {d['txt']:<20}")
                
                if d['tag'] == 'IMG': linha += f" | SRC: {d['src']}"
                if d['click']: linha += f" | ONCLICK: {d['click'][:30]}..."
                
                arquivo.write(linha + "\n")
        else:
            arquivo.write(" (Nenhum elemento interativo relevante)\n")
            
    except Exception as e:
        arquivo.write(f"ERRO JS: {e}\n")

    # 3. Mergulho Recursivo (Filhos)
    try:
        frames = driver.find_elements(By.TAG_NAME, "frame") + driver.find_elements(By.TAG_NAME, "iframe")
        
        if frames:
            arquivo.write(f" -> Mergulhando em {len(frames)} sub-frames...\n")
            
            for i in range(len(frames)):
                try:
                    driver.switch_to.frame(i)
                    _explorar_frames_recursivo(driver, arquivo, f"{hierarquia_atual} > Frame[{i}]")
                    driver.switch_to.parent_frame()
                except Exception as e:
                    arquivo.write(f"ERRO Frame[{i}]: {e}\n")
                    try: driver.switch_to.parent_frame()
                    except: pass
    except Exception as e:
        logger.warning(f"Erro ao listar subframes: {e}")