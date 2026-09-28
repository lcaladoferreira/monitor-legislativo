#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diarios/registry.py — Source Registry dos Diários Oficiais (FASE 4–6, 11).

Cada Diário Oficial (federal, estadual, municipal, judiciário) é uma **fonte
cadastrada** com identificador estável, jurisdição, forma de acesso, conector,
estado de implementação e saúde da última tentativa.

Regras de honestidade do registry:

  · fonte **sem coletor implementado** fica com `status="nao_implementado"` e
    `collector=None`. Ela aparece no painel e nas métricas de cobertura como
    pendência — nunca como cobertura;
  · fonte implementada que nunca executou fica `status="implementado"`;
    `funcionando` só depois de uma coleta com resposta verificável;
  · nenhum endereço oficial é *suposto*: `url` só é preenchido quando
    confirmado; caso contrário fica `None` e a pendência é explícita;
  · o registry guarda **definição** (código, versionado) e **saúde** (estado
    operacional, persistido em `data/legislation/diarios.json`).

Os 27 entes estaduais estão cadastrados mesmo sem coletor — é o que permite
progresso incremental sem fingir cobertura (FASE 5).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .base import (ADAPTER_FAMILIES, FORMATOS, NIVEIS, PODERES, STATUS_FONTES,
                   TIPOS_ACESSO, UFS, agora_brt, carregar_json, salvar_json, ts_iso)

ORDEM_STATUS = ("funcionando", "parcial", "falha", "implementado", "nao_implementado")


@dataclass
class FonteCadastrada:
    """Definição de uma fonte de Diário Oficial."""

    source_id: str
    nome: str
    nivel: str
    uf: str = None
    municipio: str = None
    poder: str = "nao_aplicavel"
    url: str = None
    tipo_acesso: str = "nao_definido"
    formato: str = "nao_definido"
    collector: str = None
    ativo: bool = True
    obrigatorio: bool = False
    adapter_family: str = "nao_aplicavel"
    observacao: str = None
    implementado: bool = False
    # --- saúde (runtime) ---
    status: str = "nao_implementado"
    ultima_tentativa: str = None
    ultima_execucao_ok: str = None
    ultima_publicacao: str = None
    itens_coletados: int = None
    duracao: float = None
    layout_changed: bool = None
    erro: str = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.nivel not in NIVEIS:
            raise ValueError(f"{self.source_id}: nível inválido {self.nivel!r} "
                             f"(use um de {', '.join(NIVEIS)})")
        if self.tipo_acesso not in TIPOS_ACESSO:
            raise ValueError(f"{self.source_id}: tipo_acesso inválido {self.tipo_acesso!r} "
                             f"(use um de {', '.join(TIPOS_ACESSO)})")
        if self.formato not in FORMATOS:
            raise ValueError(f"{self.source_id}: formato inválido {self.formato!r}")
        if self.adapter_family not in ADAPTER_FAMILIES:
            raise ValueError(f"{self.source_id}: adapter_family inválido "
                             f"{self.adapter_family!r}")
        if self.poder not in PODERES:
            raise ValueError(f"{self.source_id}: poder inválido {self.poder!r}")
        if not self.implementado:
            # Fonte sem coletor nunca pode se apresentar como funcional.
            self.status = "nao_implementado"
            self.collector = None
            self.tipo_acesso = "nao_definido" if self.tipo_acesso == "nao_definido" else self.tipo_acesso
        elif self.status == "nao_implementado":
            self.status = "implementado"

    # ------------------------------------------------------------------ leitura
    @property
    def jurisdicao(self):
        partes = [self.nivel]
        if self.uf:
            partes.append(self.uf)
        if self.municipio:
            partes.append(self.municipio)
        return ":".join(partes)

    def como_dict(self, incluir_saude=True):
        dados = {
            "source_id": self.source_id,
            "nome": self.nome,
            "nivel": self.nivel,
            "uf": self.uf,
            "municipio": self.municipio,
            "poder": self.poder,
            "jurisdicao": self.jurisdicao,
            "url": self.url,
            "tipo_acesso": self.tipo_acesso,
            "formato": self.formato,
            "collector": self.collector,
            "ativo": bool(self.ativo),
            "obrigatorio": bool(self.obrigatorio),
            "implementado": bool(self.implementado),
            "adapter_family": self.adapter_family,
            "observacao": self.observacao,
        }
        if incluir_saude:
            dados.update({
                "status": self.status,
                "ultima_tentativa": self.ultima_tentativa,
                "ultima_execucao_ok": self.ultima_execucao_ok,
                "ultima_publicacao": self.ultima_publicacao,
                "itens_coletados": self.itens_coletados,
                "duracao": self.duracao,
                "layout_changed": self.layout_changed,
                "erro": self.erro,
                "extra": dict(self.extra or {}),
            })
        return dados

    def atualizar_saude(self, *, status=None, ultima_tentativa=None, ultima_execucao_ok=None,
                        ultima_publicacao=None, itens_coletados=None, duracao=None,
                        layout_changed=None, erro=None, extra=None):
        """Atualiza a saúde da fonte. Fonte sem coletor não vira 'funcionando'."""
        if not self.implementado and status not in (None, "nao_implementado"):
            raise ValueError(f"{self.source_id}: fonte não implementada não pode "
                             f"receber status {status!r}")
        if status:
            if status not in STATUS_FONTES:
                raise ValueError(f"{self.source_id}: status inválido {status!r}")
            self.status = status
        for campo, valor in (("ultima_tentativa", ultima_tentativa),
                             ("ultima_execucao_ok", ultima_execucao_ok),
                             ("ultima_publicacao", ultima_publicacao),
                             ("itens_coletados", itens_coletados),
                             ("duracao", duracao), ("layout_changed", layout_changed),
                             ("erro", erro)):
            if valor is not None:
                setattr(self, campo, valor)
        if extra:
            self.extra.update(extra)
        return self


class RegistryFontes:
    """Catálogo de Diários Oficiais + saúde operacional (persistível)."""

    def __init__(self):
        self._fontes = {}

    # ------------------------------------------------------------------ cadastro
    def registrar(self, fonte):
        if fonte.source_id in self._fontes:
            raise ValueError(f"source_id duplicado no registry: {fonte.source_id}")
        self._fontes[fonte.source_id] = fonte
        return fonte

    def obter(self, source_id):
        return self._fontes.get(source_id)

    def todas(self, incluir_inativas=True):
        fontes = [f for f in self._fontes.values() if incluir_inativas or f.ativo]
        return sorted(fontes, key=lambda f: (f.nivel, f.uf or "", f.municipio or "", f.source_id))

    def por_nivel(self, nivel, incluir_inativas=True):
        return [f for f in self.todas(incluir_inativas) if f.nivel == nivel]

    def por_uf(self, uf):
        return [f for f in self.todas() if (f.uf or "").upper() == str(uf).upper()]

    def implementadas(self):
        return [f for f in self.todas() if f.implementado]

    def ativas(self):
        return [f for f in self.todas() if f.ativo]

    def fontes_com_coletor(self):
        return [f for f in self.todas() if f.ativo and f.implementado and f.collector]

    def pendentes(self):
        return [f for f in self.todas() if not f.implementado]

    # -------------------------------------------------------- saúde persistida
    def aplicar_saude(self, snapshot):
        """Aplica a saúde vinda do último snapshot (nunca inventa: só atualiza o que existe)."""
        fontes = (snapshot or {}).get("fontes") or {}
        for source_id, dados in fontes.items():
            fonte = self._fontes.get(source_id)
            if not fonte or not fonte.implementado:
                continue
            status = dados.get("status")
            if status in STATUS_FONTES and status != "nao_implementado":
                fonte.status = status
            fonte.ultima_tentativa = dados.get("ultima_tentativa") or fonte.ultima_tentativa
            fonte.ultima_execucao_ok = dados.get("ultima_execucao_ok") or fonte.ultima_execucao_ok
            fonte.ultima_publicacao = dados.get("ultima_publicacao") or fonte.ultima_publicacao
            fonte.itens_coletados = dados.get("itens_coletados", fonte.itens_coletados)
            fonte.duracao = dados.get("duracao", fonte.duracao)
            fonte.layout_changed = dados.get("layout_changed", fonte.layout_changed)
            fonte.erro = dados.get("erro", fonte.erro)
            if isinstance(dados.get("extra"), dict):
                fonte.extra.update(dados["extra"])
        return self

    def snapshot(self, com_saude=True):
        return {"gerado_em": ts_iso(),
                "fontes": {f.source_id: f.como_dict(incluir_saude=com_saude) for f in self.todas()}}

    def salvar_snapshot(self, caminho):
        return salvar_json(caminho, self.snapshot())

    @classmethod
    def de_snapshot(cls, caminho):
        return cls().aplicar_saude(carregar_json(caminho, {}) or {})

    # ----------------------------------------------------------------- resumos
    def resumo_por_status(self):
        contagem = {status: 0 for status in STATUS_FONTES}
        for fonte in self.todas():
            contagem[fonte.status] = contagem.get(fonte.status, 0) + 1
        return contagem

    def resumo_por_nivel(self):
        resumo = {}
        for fonte in self.todas():
            dados = resumo.setdefault(fonte.nivel, {"total": 0, "implementadas": 0,
                                                    "funcionando": 0, "nao_implementadas": 0})
            dados["total"] += 1
            if fonte.implementado:
                dados["implementadas"] += 1
            else:
                dados["nao_implementadas"] += 1
            if fonte.status == "funcionando":
                dados["funcionando"] += 1
        return resumo


# ------------------------------------------------------------------ cadastros
def _fontes_federais():
    """Fontes federais (DOU). Os coletores moram em `diarios/dou.py`."""
    return [
        FonteCadastrada(
            source_id="dou",
            nome="DOU — Diário Oficial da União (Imprensa Nacional)",
            nivel="federal",
            poder="todos",
            # URL oficial do serviço de leitura do DOU (verificada na sonda de 26/09/2026).
            url="https://www.in.gov.br/leitura-do-diario-oficial-da-uniao",
            tipo_acesso="html",
            formato="misto",
            collector="scripts/diarios/dou.py::ColetorDouIntegral",
            implementado=True,
            obrigatorio=True,
            adapter_family="nao_aplicavel",
            observacao=("Ingestão integral da edição (Seções 1, 2 e 3) pela página oficial "
                        "de leitura do jornal; pacote XML do INLABS suportado quando "
                        "disponível; busca temática mantida como fallback."),
        ),
        FonteCadastrada(
            source_id="dou_inlabs_xml",
            nome="DOU — pacote XML do INLABS (Imprensa Nacional)",
            nivel="federal",
            poder="todos",
            url="https://inlabs.in.gov.br/",
            tipo_acesso="xml",
            formato="xml",
            collector="scripts/diarios/dou.py::ColetorDouXMLINLABS",
            implementado=True,
            obrigatorio=False,
            observacao=("Caminho estruturado prioritário (XML oficial). O portal INLABS "
                        "exige credencial própria para download automatizado: sem "
                        "MONITOR_INLABS_USUARIO/MONITOR_INLABS_SENHA o coletor lê pacotes "
                        "locais (MONITOR_DOU_XML_DIR) e permanece 'nao_configurado' — "
                        "nunca declara cobertura que não teve."),
        ),
        FonteCadastrada(
            source_id="dou_busca_tematica",
            nome="DOU — busca temática no in.gov.br (fallback)",
            nivel="federal",
            poder="todos",
            url="https://www.in.gov.br/consulta/-/buscar/dou",
            tipo_acesso="scraper",
            formato="json",
            collector="scripts/sources/dou.py::DOU",
            implementado=True,
            obrigatorio=False,
            observacao=("Coletor histórico por termos de busca (TOPICOS_BUSCA/DISCOVERY_TERMS). "
                        "Não define cobertura: existe como redundância e verificação "
                        "complementar da ingestão integral."),
        ),
        FonteCadastrada(
            source_id="djen",
            nome="DJEN — Diário de Justiça Eletrônico Nacional (CNJ)",
            nivel="judiciario",
            poder="judiciario",
            url=None,
            tipo_acesso="nao_definido",
            formato="nao_definido",
            collector=None,
            implementado=False,
            observacao=("Cadastro criado para receber o conector das comunicações "
                        "processuais/atos do CNJ. Endereço e formato precisam ser "
                        "confirmados por sonda antes de qualquer implementação — sem "
                        "cobertura declarada até lá."),
        ),
    ]


def _fontes_estaduais():
    """Os 27 entes estaduais (26 estados + DF), cadastrados e ainda sem coletor.

    Nenhuma URL é preenchida por suposição: o endereço oficial de cada Diário
    Oficial estadual precisa ser confirmado por sonda (`scripts/probe_diarios.py`)
    antes de entrar no registry. Enquanto isso, cada fonte aparece como
    `nao_implementado` — visível no painel e nas métricas de cobertura.
    """
    nomes = {
        "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
        "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo",
        "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
        "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
        "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro",
        "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondônia",
        "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
        "SE": "Sergipe", "TO": "Tocantins",
    }
    fontes = []
    for uf in UFS:
        fontes.append(FonteCadastrada(
            source_id=f"estadual_{uf.lower()}",
            nome=f"Diário Oficial do Estado — {nomes[uf]} ({uf})",
            nivel="estadual",
            uf=uf,
            poder="todos",
            url=None,
            tipo_acesso="nao_definido",
            formato="nao_definido",
            collector=None,
            implementado=False,
            obrigatorio=False,
            observacao=("Coletor ainda não implementado. Cadastro existe para receber o "
                        "conector (preferência: XML/JSON/RSS oficial; depois listagem "
                        "HTML/PDF com detecção de layout). Nenhuma cobertura é "
                        "declarada antes de o coletor responder com dado verificável."),
        ))
    return fontes


def registry_padrao():
    """Registry com as fontes conhecidas hoje (federal/judiciário/estaduais/municipais)."""
    from .municipal import fontes_municipais_do_config
    reg = RegistryFontes()
    for fonte in _fontes_federais() + _fontes_estaduais() + fontes_municipais_do_config():
        reg.registrar(fonte)
    return reg


__all__ = ["FonteCadastrada", "RegistryFontes", "registry_padrao", "ORDEM_STATUS"]
