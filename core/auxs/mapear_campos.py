import os
from selenium.webdriver.common.by import By

def mapear_campos(driver, nome_arquivo="mapa_universal.txt"):
    """
    VARREDURA COMPLETA: Percorre recursivamente TODOS os frames e iframes
    da janela atual, independente dos nomes, e salva todos os inputs/botões.
    
    Usa JavaScript 'Jurassic' (IE5/7 compatible) para extração.
    """
    print(f"\n--- INICIANDO MAPEAMENTO UNIVERSAL ({nome_arquivo}) ---")
    
    # 1. Garante que começamos do topo da janela atual (seja ela popup ou principal)
    driver.switch_to.default_content()
    
    path_absoluto = os.path.abspath(nome_arquivo)
    
    # Abre o arquivo uma única vez para escrita
    with open(path_absoluto, "w", encoding="utf-8") as f:
        titulo = driver.title or "Sem Titulo"
        f.write(f"=== MAPA GERADO EM: {titulo} ===\n")
        f.write(f"URL: {driver.current_url}\n\n")
        
        # Chama a função recursiva interna iniciando da Raiz
        _explorar_frames_recursivo(driver, f, "ROOT")
        
    print(f"\n[FIM] Mapeamento concluído. Arquivo salvo em:\n{path_absoluto}")
    
    # Volta para o topo ao final para não deixar o driver perdido em um subframe
    driver.switch_to.default_content()

def _explorar_frames_recursivo(driver, arquivo, hierarquia_atual):
    """
    Função interna que varre o frame atual, salva dados e mergulha nos filhos.
    """
    # --- 1. IDENTIFICAÇÃO DO FRAME ATUAL ---
    try:
        nome_frame_js = driver.execute_script("return window.name")
        if not nome_frame_js: nome_frame_js = "(sem nome)"
    except:
        nome_frame_js = "Erro ao ler nome"

    print(f" > Varrendo: {hierarquia_atual} [Nome: {nome_frame_js}]")
    arquivo.write(f"\n{'='*60}\n")
    arquivo.write(f"CONTEXTO: {hierarquia_atual} | NOME INTERNO: {nome_frame_js}\n")
    arquivo.write(f"{'='*60}\n")

    # --- 2. EXTRAÇÃO DE DADOS (JURASSIC JS) ---
    js_jurassic = """
    var itens = [];
    var tags = ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON', 'A', 'IMG'];
    
    for (var t = 0; t < tags.length; t++) {
        var elementos = document.getElementsByTagName(tags[t]);
        for (var i = 0; i < elementos.length; i++) {
            var e = elementos[i];
            
            // Filtros para limpar sujeira
            if (tags[t] == 'A' && (e.innerText == null || e.innerText.replace(/^\\s+|\\s+$/g, '') == '')) continue;
            
            // Tenta pegar atributos de várias formas para garantir
            var id_attr = e.id || '';
            var name_attr = e.name || '';
            var type_attr = e.getAttribute('type') || '';
            var val_attr = e.value || '';
            var onclick = e.getAttribute('onclick') || '';
            var src = e.getAttribute('src') || '';
            var txt = e.innerText || '';
            
            itens.push({
                tag: tags[t],
                id: id_attr,
                name: name_attr,
                type: type_attr,
                val: val_attr,
                txt: txt,
                click: onclick,
                src: src
            });
        }
    }
    return itens;
    """
    
    try:
        dados = driver.execute_script(js_jurassic)
        
        if dados:
            for d in dados:
                # Formatação limpa para o arquivo
                txt_limpo = (d['txt'] or "").replace("\n", " ").strip()[:50]
                src_limpo = (d['src'] or "").split("/")[-1] # Pega só o nome do arquivo da imagem
                
                linha = (f"TAG: {d['tag']:<7} | "
                         f"ID: {d['id']:<15} | "
                         f"NAME: {d['name']:<20} | "
                         f"VAL: {d['val']:<15} | "
                         f"TXT: {txt_limpo:<20}")
                
                # Adiciona info extra se for relevante
                if d['tag'] == 'IMG':
                    linha += f" | SRC: {src_limpo}"
                if d['click']:
                    linha += f" | ONCLICK: {d['click'][:30]}..."
                
                arquivo.write(linha + "\n")
        else:
            arquivo.write(" (Nenhum elemento interativo encontrado neste frame)\n")
            
    except Exception as e:
        arquivo.write(f"ERRO DE JS NO FRAME: {e}\n")

    # --- 3. MERGULHO RECURSIVO (BUSCA FILHOS) ---
    # Encontra frames e iframes
    sub_frames = driver.find_elements(By.TAG_NAME, "frame") + driver.find_elements(By.TAG_NAME, "iframe")
    
    if sub_frames:
        arquivo.write(f" -> Encontrados {len(sub_frames)} sub-frames aqui. Mergulhando...\n")
        
        # Iteramos por índice para evitar referências 'stale'
        for i in range(len(sub_frames)):
            try:
                # Entra no frame filho
                driver.switch_to.frame(i)
                
                # CHAMA A SI MESMO (Recursão)
                novo_path = f"{hierarquia_atual} > Frame[{i}]"
                _explorar_frames_recursivo(driver, arquivo, novo_path)
                
                # IMPORTANTE: Volta para o frame pai para continuar o loop
                driver.switch_to.parent_frame()
                
            except Exception as e:
                arquivo.write(f"ERRO ao acessar sub-frame {i}: {e}\n")
                # Tenta voltar ao pai para não quebrar o loop todo
                try: driver.switch_to.parent_frame()
                except: pass