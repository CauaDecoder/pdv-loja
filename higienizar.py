import csv
import re

input_file = 'products.csv'
output_file = 'produtos_limpo.csv'

with open(input_file, mode='r', encoding='utf-8') as infile, \
     open(output_file, mode='w', encoding='utf-8', newline='') as outfile:
    
    # O arquivo original do Conta Azul usa ponto e vírgula
    reader = csv.DictReader(infile, delimiter=';')
    
    # O novo arquivo usará as colunas padronizadas exigidas
    fieldnames = ['codigo', 'nome', 'preco', 'estoque']
    writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=',')
    
    writer.writeheader()
    produtos_vistos = set()
    
    for row in reader:
        codigo = row.get('Código', '').strip()
        nome = row.get('Nome do Produto', '').strip()
        
        if not codigo or not nome:
            continue
            
        # 1.4 - Remove itens perfeitamente duplicados na importação
        nome_upper = nome.upper()
        if nome_upper in produtos_vistos:
            continue
        produtos_vistos.add(nome_upper)
        
        # 1.3 - Limpa o preço (remove 'R$ ' e troca vírgula por ponto)
        preco_bruto = row.get('Valor de Venda', '0')
        preco_limpo = re.sub(r'[^\d,]', '', preco_bruto)
        preco_limpo = preco_limpo.replace(',', '.')
        if not preco_limpo:
            preco_limpo = '0.00'
            
        estoque = row.get('Qt. Estoque', '0').strip()
        if not estoque:
            estoque = '0'
            
        writer.writerow({
            'codigo': codigo,
            'nome': nome,
            'preco': preco_limpo,
            'estoque': estoque
        })

print("Higienização concluída! O arquivo 'produtos_limpo.csv' foi gerado.")