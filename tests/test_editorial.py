#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_editorial.py — Testes offline da camada editorial (/artigos/).

Cobrem os invariantes da missão editorial, SEM rede e SEM tocar o dataset real:
dataset de teste é montado em diretório temporário e o motor editorial
(scripts/generate_articles.py) é executado com caminhos explícitos.

Cenários (1–20 conforme especificação da área de artigos):
 1. nenhuma mudança nova → nenhuma ação editorial (arquivos byte-estáveis)
 2. mudança relevante sem artigo correspondente → novo artigo
 3. segunda execução da mesma mudança → nada duplicado
 4. duas candidatas a artigo novo no mesmo dia → apenas a mais relevante cria URL
 5. mudança de artigo existente → atualiza a mesma URL
 6. atualização não consome a quota diária de artigo novo
 7. três atualizações no mesmo dia → três artigos atualizados
 8. artigo atualizado preserva published_at
 9. artigo atualizado recebe novo modified_at
10. artigo atualizado incrementa revision_count
11. artigo atualizado preserva mudanças anteriores no histórico
12. atualização irrelevante → nenhuma alteração de artigo
13. novo fato autônomo → novo artigo somente com justificativa registrada
14. artigo novo entra no sitemap
15. atualização altera apenas <lastmod>, não <loc>
16. JSON-LD reflete datePublished e dateModified
17. canonical permanece estável
18. links artigo ↔ proposição permanecem válidos
19. mecanismos de IA refletem artigo atualizado
20. monitor legislativo antigo continua funcionando (dataset intacto + build/validate)
"""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

import generate_articles as ga  # noqa: E402
import build_articles as ba     # noqa: E402
import ai_visibility            # noqa: E402

SITE = "https://monitor.lcfconsulting.com.br"


# ------------------------------------------------------------------ fixtures
def _prop(pid="camara_pl_1001_2026", tipo="PL", numero=1001, ano=2026,
          titulo="Regulamentação da inteligência artificial no setor público",
          score=80):
    return {
        "id": pid, "tipo": tipo, "numero": numero, "ano": ano, "titulo": titulo,
        "ementa": "Dispõe sobre o uso responsável de inteligência artificial.",
        "casa_origem": "Câmara dos Deputados", "casa_atual": "Câmara dos Deputados",
        "url_oficial": f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={numero}",
        "situacao": "Aguardando Parecer do(a) Relator(a)",
        "impacto": {"score": score, "classificacao": "MUITO RELEVANTE"},
        "relator": {"nome": "Deputada Teste", "partido": "XX", "estado": "DF"},
        "categorias": [], "proxima_etapa": "Parecer do relator.",
        "timeline": [{"data": "2026-01-10", "evento": "Apresentada a proposição.",
                      "fonte": "https://www.camara.leg.br/"}],
    }


def _mud(titulo, tipo="sanção", prop="camara_pl_1001_2026", data="2026-03-01",
         deteccao="2026-03-01", run="run_teste_1", relevancia=None,
         pendente=False, descricao="Fato registrado na ficha oficial."):
    m = {
        "data": data, "titulo": titulo, "descricao": descricao, "tipo": tipo,
        "proposicao": prop, "fonte_url": "https://www.camara.leg.br/x",
        "campo_alterado": "situacao", "valor_anterior": "A", "valor_novo": "B",
        "fonte": "Câmara dos Deputados — API oficial", "url_oficial": "https://www.camara.leg.br/x",
        "data_deteccao": deteccao, "id_execucao": run,
        "timestamp_execucao": f"{deteccao}T10:00:00-03:00",
        "revisao_pendente": pendente,
    }
    if relevancia:
        m["relevancia"] = relevancia
    return m


class DatasetFixture:
    """Dataset mínimo e determinístico em diretório temporário."""

    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="editorial-test-")
        self.leg = os.path.join(self.tmp, "legislation")
        self.art = os.path.join(self.tmp, "articles")
        os.makedirs(self.leg)
        self.props = [_prop(), _prop(pid="camara_pl_1002_2026", numero=1002,
                                     titulo="Rotulagem de conteúdo sintético",
                                     score=70)]
        # mudança padrão: fato forte (sanção) do PL 1001, detectada em 2026-03-01
        self.mudancas = [_mud("Sancionada a matéria PL 1001/2026",
                              tipo="sanção", prop="camara_pl_1001_2026",
                              data="2026-03-01", deteccao="2026-03-01",
                              run="run_teste_1")]
        self.gravar()

    def gravar(self):
        arquivos = {
            "propositions.json": {"meta": {}, "proposicoes": self.props},
            "updates.json": {"meta": {}, "mudancas": self.mudancas, "execucoes": []},
            "atos.json": {"meta": {}, "atos": [], "indice": {}},
            "laws.json": {"meta": {}, "normas": []},
            "categories.json": {"meta": {}, "categorias": []},
            "parliamentarians.json": {"meta": {}, "parlamentares": []},
            "events.json": {"meta": {}, "eventos": []},
            "timeline.json": {"meta": {}, "eventos": []},
        }
        for nome, dados in arquivos.items():
            with open(os.path.join(self.leg, nome), "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False)

    def cfg(self, **kw):
        base = {"data_dir": self.leg, "art_dir": self.art,
                "max_new_per_day": 1, "stale_days": 30,
                "min_score_novo_assunto": 75, "new_min_score": 12,
                "dry_run": False, "bootstrap": False, "run_id": "teste"}
        base.update(kw)
        return base

    def rodar(self, **kw):
        return ga.run_editorial(self.cfg(**kw), logger=lambda *_: None)

    def artigos(self):
        return ga.load_artigos(self.art)

    def estado(self):
        return ga.load_state(self.art)

    def limpar(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and "href" in a:
            self.links.append(a["href"])


# ------------------------------------------------------------------ testes
class Base(unittest.TestCase):
    def setUp(self):
        self.fx = DatasetFixture()

    def tearDown(self):
        self.fx.limpar()


class TesteAcoesEditoriais(Base):

    def test_01_sem_mudanca_nova_nenhuma_acao(self):
        self.fx.rodar()  # primeira execução já processa tudo
        antes_art = Path(self.fx.art, "articles.json").read_bytes()
        # segunda execução no MESMO dia, sem mudanças novas
        r2 = self.fx.rodar()
        self.assertEqual(r2["mudancas_novas"], 0)
        self.assertEqual(r2["novos_artigos"] + r2["artigos_atualizados"] + r2["ignoradas"], 0)
        depois_art = Path(self.fx.art, "articles.json").read_bytes()
        self.assertEqual(antes_art, depois_art,
                         "execução sem novidades reescreveu articles.json")
        state = self.fx.estado()
        self.assertEqual(len(state["processadas"]),
                         sum(1 for _ in self.fx.mudancas))

    def test_02_mudanca_relevante_sem_artigo_cria_artigo(self):
        self.fx.rodar(bootstrap=True)  # dia editorial = dia de detecção (determinístico)
        arts = self.fx.artigos()["artigos"]
        self.assertEqual(len(arts), 1)
        a = arts[0]
        self.assertEqual(a["status"], "published")
        self.assertTrue(a["editorial_topic_id"].startswith("pl-1001-2026"))
        self.assertEqual(a["published_at"], "2026-03-01")
        self.assertTrue(a["slug"] and a["url"].startswith("artigos/"))

    def test_03_segunda_execucao_nao_duplica(self):
        self.fx.rodar()
        r2 = self.fx.rodar()
        arts = self.fx.artigos()["artigos"]
        self.assertEqual(len(arts), 1, "segunda execução criou artigo duplicado")
        self.assertEqual(r2["novos_artigos"], 0)
        # nenhuma mudança processada duas vezes
        state = self.fx.estado()
        cids = list(state["processadas"].keys())
        self.assertEqual(len(cids), len(set(cids)))
        self.assertEqual(len(cids), len(self.fx.mudancas))

    def test_04_duas_candidatas_mesmo_dia_so_a_mais_relevante(self):
        # duas proposições fortes, mudanças 'nova proposição' no mesmo dia
        p1 = _prop(pid="camara_pl_2001_2026", numero=2001,
                   titulo="Marco geral de IA", score=95)
        p2 = _prop(pid="camara_pl_2002_2026", numero=2002,
                   titulo="Programa pontual de IA", score=60)
        self.fx.props = [p1, p2]
        self.fx.mudancas = [
            _mud("Nova proposição: PL 2001/2026", tipo="nova proposição",
                 prop=p1["id"], deteccao="2026-03-01"),
            _mud("Nova proposição: PL 2002/2026", tipo="nova proposição",
                 prop=p2["id"], deteccao="2026-03-01"),
        ]
        self.fx.gravar()
        self.fx.rodar()
        arts = self.fx.artigos()["artigos"]
        self.assertEqual(len(arts), 1, "cota diária de novo artigo violada")
        self.assertIn("pl-2001-2026", arts[0]["editorial_topic_id"],
                      "não escolheu a mais relevante")
        # a segunda fica pendente (sem perder o fato)
        pend = self.fx.estado()["pendentes"]
        self.assertEqual(len(pend), 1)
        self.assertIn("pl-2002-2026", list(pend.values())[0]["editorial_topic_id"])

    def test_05_mudanca_de_artigo_existente_atualiza_mesma_url(self):
        self.fx.mudancas = [
            _mud("Aprovado na comissão", tipo="aprovação", data="2026-03-01",
                 deteccao="2026-03-01"),
            _mud("Novo relator designado", tipo="relatoria", data="2026-03-05",
                 deteccao="2026-03-05", run="run_teste_2"),
        ]
        self.fx.gravar()
        self.fx.rodar(bootstrap=True)
        arts = self.fx.artigos()["artigos"]
        self.assertEqual(len(arts), 1)
        self.assertEqual(arts[0]["revision_count"], 2)
        # mesma URL (slug estável) — nenhum /pl-1001-novo-relator/
        self.assertNotIn("novo-relator", arts[0]["slug"])

    def test_06_atualizacao_nao_consome_quota_de_artigo_novo(self):
        # dia 1: cria artigo do PL 1001 E recebe atualização do mesmo assunto;
        # a cota continua 1 e a atualização foi aplicada mesmo com cota cheia.
        self.fx.mudancas = [
            _mud("Aprovado na comissão", tipo="aprovação", data="2026-03-01",
                 deteccao="2026-03-01"),
            _mud("Parecer apresentado", tipo="parecer", data="2026-03-02",
                 deteccao="2026-03-02", run="run_teste_2"),
            _mud("Sanção presidencial", tipo="sanção", data="2026-03-03",
                 deteccao="2026-03-03", run="run_teste_3"),
        ]
        self.fx.gravar()
        self.fx.rodar(bootstrap=True)
        arts = self.fx.artigos()["artigos"]
        self.assertEqual(len(arts), 1, "nenhum segundo assunto deveria criar URL")
        self.assertEqual(arts[0]["revision_count"], 3)
        por_dia = {}
        for a in arts:
            por_dia[a["published_at"]] = por_dia.get(a["published_at"], 0) + 1
        self.assertTrue(all(n <= 1 for n in por_dia.values()))

    def test_07_tres_atualizacoes_mesmo_dia_tres_artigos(self):
        p2 = _prop(pid="camara_pl_1002_2026", numero=1002,
                   titulo="Rotulagem de conteúdo sintético", score=80)
        p3 = _prop(pid="camara_pl_1003_2026", numero=1003,
                   titulo="Auditoria algorítmica", score=80)
        self.fx.props = [self.fx.props[0], p2, p3]
        # criação em dias distintos (cota 1/dia)
        self.fx.mudancas = [
            _mud("Aprovado PL 1001", tipo="aprovação", prop="camara_pl_1001_2026",
                 deteccao="2026-03-01"),
            _mud("Aprovado PL 1002", tipo="aprovação", prop=p2["id"],
                 deteccao="2026-03-02", run="r2"),
            _mud("Aprovado PL 1003", tipo="aprovação", prop=p3["id"],
                 deteccao="2026-03-03", run="r3"),
            # três atualizações NO MESMO dia
            _mud("Relator novo PL 1001", tipo="relatoria",
                 prop="camara_pl_1001_2026", deteccao="2026-03-04", run="r4"),
            _mud("Relator novo PL 1002", tipo="relatoria", prop=p2["id"],
                 deteccao="2026-03-04", run="r5"),
            _mud("Relator novo PL 1003", tipo="relatoria", prop=p3["id"],
                 deteccao="2026-03-04", run="r6"),
        ]
        self.fx.gravar()
        self.fx.rodar(bootstrap=True)
        arts = self.fx.artigos()["artigos"]
        self.assertEqual(len(arts), 3)
        atualizados = [a for a in arts if a["revision_count"] >= 2]
        self.assertEqual(len(atualizados), 3, "os três artigos deveriam ser atualizados")

    def test_08_a_09_a_10_datas_e_revision_count(self):
        self.fx.mudancas = [
            _mud("Aprovado na comissão", tipo="aprovação", data="2026-03-01",
                 deteccao="2026-03-01"),
            _mud("Parecer apresentado", tipo="parecer", data="2026-03-02",
                 deteccao="2026-03-05", run="r2"),
        ]
        self.fx.gravar()
        self.fx.rodar(bootstrap=True)
        a = self.fx.artigos()["artigos"][0]
        self.assertEqual(a["published_at"], "2026-03-01",
                         "published_at mudou em atualização")
        self.assertEqual(a["modified_at"], "2026-03-05",
                         "modified_at não refletiu a atualização")
        self.assertEqual(a["revision_count"], 2)

    def test_11_historico_preservado(self):
        self.fx.mudancas = [
            _mud("Aprovado na comissão", tipo="aprovação", data="2026-03-01",
                 deteccao="2026-03-01"),
            _mud("Parecer apresentado", tipo="parecer", data="2026-03-02",
                 deteccao="2026-03-05", run="r2"),
        ]
        self.fx.gravar()
        self.fx.rodar(bootstrap=True)
        a = self.fx.artigos()["artigos"][0]
        datas = [r["date"] for r in a["revisions"]]
        self.assertEqual(datas[0], a["published_at"],
                         "revisão de criação não é a primeira do histórico")
        self.assertIn("2026-03-05", datas)
        self.assertTrue(a["revisions"][0]["source_change_ids"],
                        "criação sem source_change_ids")
        self.assertTrue(set(a["revisions"][1]["source_change_ids"]).isdisjoint(
            a["revisions"][0]["source_change_ids"]), "mesma mudança em duas revisões")

    def test_12_mudanca_irrelevante_nada_altera(self):
        self.fx.rodar()
        antes = self.fx.artigos()["artigos"][0]
        hash_antes = antes["editorial_hash"]
        rev_antes = antes["revision_count"]
        self.fx.mudancas.append(_mud(
            "EXTRATO DE TERMO ADITIVO Nº 1/2026 - UASG 560010",
            tipo="nova publicação", prop=None, deteccao="2026-03-06", run="r3"))
        self.fx.gravar()
        r = self.fx.rodar()
        a = self.fx.artigos()["artigos"][0]
        self.assertEqual(a["editorial_hash"], hash_antes)
        self.assertEqual(a["revision_count"], rev_antes)
        self.assertEqual(a["modified_at"], antes["modified_at"])
        st = self.fx.estado()
        cid = ga.change_id(self.fx.mudancas[-1])
        self.assertEqual(st["processadas"][cid]["editorial_action"], "ignored")

    def test_13_novo_fato_autonomo_com_justificativa_registrada(self):
        # o PL 1001 já tem artigo; fato AUTÔNOMO de outro assunto (PL 1002
        # sancionado como lei própria) gera artigo novo — com justificativa.
        p2 = _prop(pid="camara_pl_1002_2026", numero=1002,
                   titulo="Rotulagem de conteúdo sintético", score=78)
        self.fx.props = [self.fx.props[0], p2]
        self.fx.mudancas = [
            _mud("Aprovado PL 1001", tipo="aprovação", prop="camara_pl_1001_2026",
                 deteccao="2026-03-01"),
            _mud("Sancionada a lei de rotulagem", tipo="sanção", prop=p2["id"],
                 deteccao="2026-03-02", run="r2"),
        ]
        self.fx.gravar()
        self.fx.rodar(bootstrap=True)
        arts = self.fx.artigos()["artigos"]
        self.assertEqual(len(arts), 2, "fato autônomo deveria criar URL própria")
        state = self.fx.estado()
        cid2 = ga.change_id(self.fx.mudancas[1])
        reg = state["processadas"][cid2]
        self.assertEqual(reg["editorial_action"], "new_article")
        self.assertTrue(reg["selection_reason"], "criação sem justificativa registrada")
        self.assertTrue(reg["article_id"] and reg["editorial_topic_id"])


class TesteIntegracaoSite(unittest.TestCase):
    """Testes 14–19: build do site, sitemap, JSON-LD e mecanismos de IA."""

    @classmethod
    def setUpClass(cls):
        # dataset editorial de teste com criação + atualização
        cls.tmp = tempfile.mkdtemp(prefix="editorial-site-")
        fx = DatasetFixture()
        fx.mudancas = [
            _mud("Aprovado na comissão", tipo="aprovação", data="2026-03-01",
                 deteccao="2026-03-01"),
            _mud("Parecer apresentado", tipo="parecer", data="2026-03-02",
                 deteccao="2026-03-05", run="r2"),
        ]
        fx.gravar()
        fx.rodar(bootstrap=True)
        cls.artigos_f = fx.artigos()
        cls.fx = fx

        # núcleo real do gerador com OUT redirecionado para o temp
        import build_site_core as core
        core.SITE_URL = SITE
        core.OUT = cls.tmp
        core._SITEMAP_LASTMOD = {}
        cls.core = core
        n = ba.build(core, cls.artigos_f)
        assert n >= 2, "área de artigos não foi gerada"

    @classmethod
    def tearDownClass(cls):
        cls.fx.limpar()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _artigo(self):
        return self.artigos_f["artigos"][0]

    def test_14_artigo_novo_no_sitemap(self):
        self.core.build_sitemap(["", "artigos/"] + [
            f"artigos/{a['slug']}/" for a in self.artigos_f["artigos"]])
        xml = Path(self.tmp, "sitemap.xml").read_text(encoding="utf-8")
        root = ET.fromstring(xml)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [u.text for u in root.findall("s:url/s:loc", ns)]
        slug = self._artigo()["slug"]
        self.assertIn(f"{SITE}/artigos/{slug}/", urls)
        self.assertEqual(urls.count(f"{SITE}/artigos/{slug}/"), 1)

    def test_15_atualizacao_altera_lastmod_e_nao_loc(self):
        a = self._artigo()
        loc = f"{SITE}/artigos/{a['slug']}/"
        # build ANTES e DEPOIS da atualização mantém o loc; lastmod segue modified_at
        self.core._SITEMAP_LASTMOD.clear()
        self.core._SITEMAP_LASTMOD[loc[len(SITE) + 1:]] = a["modified_at"]
        self.core.build_sitemap(["", loc[len(SITE) + 1:]])
        xml = Path(self.tmp, "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn(f"<loc>{loc}</loc><lastmod>{a['modified_at']}</lastmod>", xml)
        self.assertEqual(xml.count(f"<loc>{loc}</loc>"), 1)
        # a URL do artigo no dataset nunca muda com a atualização
        self.assertEqual(a["url"], f"artigos/{a['slug']}/")
        self.assertEqual(a["published_at"], "2026-03-01")
        self.assertEqual(a["modified_at"], "2026-03-05")

    def test_16_jsonld_datas(self):
        a = self._artigo()
        ld = ba.article_jsonld(SITE, a)
        self.assertEqual(ld["@type"], "NewsArticle")
        self.assertEqual(ld["datePublished"], "2026-03-01")
        self.assertEqual(ld["dateModified"], "2026-03-05")
        self.assertEqual(ld["author"][0]["name"], "Leandro Calado")
        self.assertEqual(ld["publisher"]["name"], "LCF Consulting")
        self.assertTrue(ld["mainEntityOfPage"]["@id"].startswith(SITE + "/artigos/"))
        self.assertTrue(ld["keywords"])
        self.assertTrue(ld["about"])

    def test_17_canonical_estavel(self):
        a = self._artigo()
        html = Path(self.tmp, "artigos", a["slug"], "index.html").read_text(encoding="utf-8")
        canon = re.search(r'<link rel="canonical" href="([^"]+)"', html).group(1)
        self.assertEqual(canon, f"{SITE}/artigos/{a['slug']}/")
        # canonical não depende de modified_at
        self.assertNotIn(a["modified_at"], canon)

    def test_18_links_artigo_proposicao_validos(self):
        a = self._artigo()
        html = Path(self.tmp, "artigos", a["slug"], "index.html").read_text(encoding="utf-8")
        m = Markup()
        m.feed(html)
        # artigo → ficha da proposição (fonte oficial)
        self.assertTrue(any("camara.leg.br/proposicoesWeb" in l for l in m.links),
                        "artigo sem link para a ficha oficial")
        # dataset ↔ proposição
        self.assertIn("camara_pl_1001_2026", a["related_propositions"])
        # e a ligação inversa existe no gerador de fichas
        self.assertTrue(ba.artigos_para_prop(self.artigos_f, "camara_pl_1001_2026"))

    def test_19_mecanismos_de_ia_refletem_atualizacao(self):
        class Stub:
            SITE_URL = SITE
            BASE = ""
        bloco = ai_visibility.secao_artigos_llms(Stub(), self.artigos_f["artigos"])
        a = self._artigo()
        self.assertIn(f"/artigos/{a['slug']}/", bloco)
        self.assertIn(f"atualizado {a['modified_at']}", bloco)
        bloco_full = ai_visibility.secao_artigos_llms_full(Stub(), self.artigos_f["artigos"])
        self.assertIn("dateModified não" if False else f"modified {a['modified_at']}", bloco_full)


class TesteMonitorAntigo(unittest.TestCase):
    def test_20_dataset_legislativo_intacto_e_build_valida(self):
        # 20a) rodar a camada editorial NÃO altera nenhum arquivo do dataset
        tmp = tempfile.mkdtemp(prefix="editorial-leg-")
        leg = os.path.join(tmp, "legislation")
        shutil.copytree(os.path.join(BASE, "data", "legislation"), leg)
        antes = {}
        for nome in os.listdir(leg):
            with open(os.path.join(leg, nome), "rb") as f:
                antes[nome] = f.read()
        r = ga.run_editorial({"data_dir": leg, "art_dir": os.path.join(tmp, "articles"),
                              "bootstrap": True, "run_id": "teste20"},
                             logger=lambda *_: None)
        self.assertIsNone(r["erro"])
        for nome, conteudo in antes.items():
            with open(os.path.join(leg, nome), "rb") as f:
                self.assertEqual(conteudo, f.read(),
                                 f"dataset legislativo alterado: {nome}")
        shutil.rmtree(tmp, ignore_errors=True)

        # 20b) build + validação do site REAL continuam passando
        import subprocess
        r1 = subprocess.run([sys.executable, os.path.join(BASE, "scripts", "build_site.py")],
                            capture_output=True, text=True, cwd=BASE)
        self.assertEqual(r1.returncode, 0, r1.stderr[-400:])
        r2 = subprocess.run([sys.executable, os.path.join(BASE, "scripts", "validate_site.py")],
                            capture_output=True, text=True, cwd=BASE)
        self.assertEqual(r2.returncode, 0, r2.stdout[-400:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
