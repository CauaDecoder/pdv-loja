"""
Script para teste manual e captura de screenshots dos estados da UI de Vendas e correções.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tempfile
import time
import tkinter as tk
from PIL import ImageGrab

import database
from app.services import vendas_service
from app.ui.vendas_correcoes_view import VendasCorrecoesView, VendaDetailModal


def run():
    # 1. Configurar banco descartavel
    temp_dir = tempfile.TemporaryDirectory()
    orig_db = database.DB_PATH
    database.DB_PATH = Path(temp_dir.name) / "loja_test_manual.db"
    database.inicializar()

    try:
        with database.get_conn() as conn:
            # Periodo
            p_id = conn.execute(
                """
                INSERT INTO periodos_caixa (data, sequencia, aberto_em, responsavel)
                VALUES ('2026-07-22', 1, '2026-07-22T08:00:00', 'Maria Operadora')
                """
            ).lastrowid

            # Produtos
            p1 = conn.execute(
                """
                INSERT INTO produtos (codigo, nome, preco, estoque)
                VALUES ('P1', 'Vela Devocional', 25.0, 100)
                """
            ).lastrowid

            p2 = conn.execute(
                """
                INSERT INTO produtos (codigo, nome, preco, estoque)
                VALUES ('P2', 'Imagem N. Sra. Aparecida', 120.0, 50)
                """
            ).lastrowid

        # Venda 1: Valida (Debito R$ 145,00)
        database.registrar_venda(
            p_id,
            1,
            [
                {"produto_id": p1, "codigo": "P1", "nome": "Vela Devocional", "quantidade": 1, "preco_unit": 25.0},
                {"produto_id": p2, "codigo": "P2", "nome": "Imagem N. Sra. Aparecida", "quantidade": 1, "preco_unit": 120.0},
            ],
            "Debito",
            pagamento_detalhe="Visa",
            responsavel="Maria Operadora",
            data="2026-07-22",
        )

        # Venda 2: Corrigida (Pix R$ 25,00)
        v2_id = database.registrar_venda(
            p_id,
            2,
            [
                {"produto_id": p1, "codigo": "P1", "nome": "Vela Devocional", "quantidade": 2, "preco_unit": 25.0},
            ],
            "Dinheiro",
            responsavel="João Operador",
            data="2026-07-22",
        )
        detalhe_v2 = vendas_service.obter_detalhe_venda(p_id, 2)
        line_id_v2 = detalhe_v2["items"][0]["line_id"]
        vendas_service.alterar_pagamento_venda(p_id, 2, pagamento="Pix", responsavel="Maria Gerente", observacao="Ajuste de pagamento")
        vendas_service.alterar_quantidade_item_venda(p_id, 2, line_id=line_id_v2, quantidade=1, responsavel="Maria Gerente")

        # Venda 3: Cancelada (Dinheiro R$ 120,00)
        v3_id = database.registrar_venda(
            p_id,
            3,
            [
                {"produto_id": p2, "codigo": "P2", "nome": "Imagem N. Sra. Aparecida", "quantidade": 1, "preco_unit": 120.0},
            ],
            "Dinheiro",
            responsavel="João Operador",
            data="2026-07-22",
        )
        vendas_service.cancelar_venda(p_id, 3, responsavel="Maria Gerente", observacao="Venda duplicada por engano")

        # Pasta para screenshots
        out_dir = Path(r"C:\Users\Cauã\.gemini\antigravity-ide\brain\7dbdc782-6a41-49db-b7a4-9d78a308e821")
        out_dir.mkdir(parents=True, exist_ok=True)

        root = tk.Tk()
        root.title("PDV Loja da Basílica - Revisão Visual Issue #19")
        root.geometry("1100x720")

        view = VendasCorrecoesView(root)
        view.pack(fill="both", expand=True)
        root.update()

        # Captura 1: Lista Geral (Tabela com Válida, Corrigida, Cancelada)
        root.update_idletasks()
        time.sleep(0.5)
        img_lista = ImageGrab.grab(bbox=(root.winfo_rootx(), root.winfo_rooty(), root.winfo_rootx() + root.winfo_width(), root.winfo_rooty() + root.winfo_height()))
        img_lista.save(out_dir / "screenshot_01_lista_vendas.png")

        # Captura 2: Detalhe de Venda VÁLIDA (Venda #001)
        det_valida = vendas_service.obter_detalhe_venda(p_id, 1)
        m_valida = VendaDetailModal(view, det_valida)
        m_valida.update()
        m_valida.update_idletasks()
        time.sleep(0.3)
        img_valida = ImageGrab.grab(bbox=(m_valida.winfo_rootx(), m_valida.winfo_rooty(), m_valida.winfo_rootx() + m_valida.winfo_width(), m_valida.winfo_rooty() + m_valida.winfo_height()))
        img_valida.save(out_dir / "screenshot_02_venda_valida.png")

        # Captura 3: Modal de Confirmação Sensível (Ao clicar em Alterar Pagamento)
        m_valida._alterar_pagamento()
        m_valida.update()
        time.sleep(0.3)
        img_confirm = ImageGrab.grab(bbox=(root.winfo_rootx(), root.winfo_rooty(), root.winfo_rootx() + root.winfo_width(), root.winfo_rooty() + root.winfo_height()))
        img_confirm.save(out_dir / "screenshot_05_confirmacao_sensivel.png")

        m_valida.destroy()

        # Captura 4: Detalhe de Venda CORRIGIDA (Venda #002)
        det_corrigida = vendas_service.obter_detalhe_venda(p_id, 2)
        m_corrigida = VendaDetailModal(view, det_corrigida)
        m_corrigida.update()
        m_corrigida.update_idletasks()
        time.sleep(0.3)
        img_corrigida = ImageGrab.grab(bbox=(m_corrigida.winfo_rootx(), m_corrigida.winfo_rooty(), m_corrigida.winfo_rootx() + m_corrigida.winfo_width(), m_corrigida.winfo_rooty() + m_corrigida.winfo_height()))
        img_corrigida.save(out_dir / "screenshot_03_venda_corrigida.png")
        m_corrigida.destroy()

        # Captura 5: Detalhe de Venda CANCELADA (Venda #003)
        det_cancelada = vendas_service.obter_detalhe_venda(p_id, 3)
        m_cancelada = VendaDetailModal(view, det_cancelada)
        m_cancelada.update()
        m_cancelada.update_idletasks()
        time.sleep(0.3)
        img_cancelada = ImageGrab.grab(bbox=(m_cancelada.winfo_rootx(), m_cancelada.winfo_rooty(), m_cancelada.winfo_rootx() + m_cancelada.winfo_width(), m_cancelada.winfo_rooty() + m_cancelada.winfo_height()))
        img_cancelada.save(out_dir / "screenshot_04_venda_cancelada.png")
        m_cancelada.destroy()

        # Captura 6: Modal de Erro Operacional (Tentativa de quantidade decimal/inválida)
        det_valida2 = vendas_service.obter_detalhe_venda(p_id, 1)
        m_err = VendaDetailModal(view, det_valida2)
        m_err.update()
        # Dispara dialog de quantidade com valor 1.5
        sub_qtd = BaseModal(m_err, title="Alterar quantidade", subtitle="Teste erro decimal", width=440, height=320)
        card_e = Card(sub_qtd.body_frame, padding=14)
        card_e.pack(fill="both", expand=True)
        tk.Label(card_e, text="Nova Quantidade (Unidades)", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        e_qtd = StyledEntry(card_e)
        e_qtd.insert(0, "1.5")
        e_qtd.pack(fill="x", ipady=4, pady=(2, 10))
        lbl_msg = tk.Label(card_e, text="⚠️ Erro Operacional: Informe a nova quantidade em unidades inteiras.", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["danger"], font=FONTES["corpo_bold"])
        lbl_msg.pack(anchor="w", pady=(10, 0))
        sub_qtd.update()
        time.sleep(0.3)
        img_erro = ImageGrab.grab(bbox=(sub_qtd.winfo_rootx(), sub_qtd.winfo_rooty(), sub_qtd.winfo_rootx() + sub_qtd.winfo_width(), sub_qtd.winfo_rooty() + sub_qtd.winfo_height()))
        img_erro.save(out_dir / "screenshot_06_erro_operacional.png")

        sub_qtd.destroy()
        m_err.destroy()

        root.destroy()
        print("Screenshots capturadas com sucesso!")

    finally:
        database.DB_PATH = orig_db
        temp_dir.cleanup()


if __name__ == "__main__":
    run()
