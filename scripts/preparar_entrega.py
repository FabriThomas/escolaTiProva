#!/usr/bin/env python3
"""Reage a edicoes/comentarios na ISSUE UNICA da prova (lock .prova/issue).

Valida a preparacao (ALUNO.md com RA, identidade, FONTES.md editado, variante)
e — se a prova ja foi aplicada — a variante, e responde NA PROPRIA ISSUE
(comentario; NAO fecha: o fechamento encerra a prova — ver fechar_prova.py).

ROTEAMENTO (v3.5, v3.7): responde APENAS para (a) evento `issues: edited`,
(b) comentario que case `/track <nome>` (selecao), (c) `/ajuda`/`--help` ou
(d) `/aplicar` (apenas o aviso de descontinuacao — o comando morreu:
a aplicacao e consequencia direta do `/track`).
Qualquer OUTRO comentario (`/auto-correcao`, conversa do aluno) e SILENCIO
TOTAL — o bug do roteamento respondia a qualquer comentario repetindo a
selecao do `.prova/track` atual.

Selecao `/track <nome>` (issueops):
- valida o nome contra as candidatas do template (scripts/selecao.py);
- comenta o feedback NA HORA (modo sandbox para o dummy / erro listando as
  opcoes); e, se valido, grava `.prova/track` em commit de BOT e da PUSH —
  e o push dispara o aplicar-prova na hora (aplicacao em cadeia).

UPSERT (v3.6): o comentario de estado ("Preparacao em dia/incompleta") e o
ack de selecao (sandbox) sao EDITADOS no mesmo comentario (marcadores
`<!-- preparacao -->` / `<!-- track-ack -->`) em vez de criados de novo —
rajadas de `issues: edited` (varios checkboxes) disparam varios runs e o
cancel-in-progress do concurrency pode nao impedir que dois scripts passem
pela porta ao mesmo tempo (caso real: comentario duplicado no beta).

FONTES.md: presente E EDITADO em relacao ao template (fetch `prova-template`,
`git show FETCH_HEAD:FONTES.md`) — identico ao template gera alerta de edicao.

No-op silencioso se a issue do evento nao for a da prova.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
from variante import slug_do_repo, pasta_do_ano, variante  # noqa: E402
import prova_issue  # noqa: E402
import selecao  # noqa: E402
import track_lock  # noqa: E402

TOKEN = os.environ.get("GH_TOKEN", "")
REPO_FULL = os.environ.get("REPO_FULL", "")
NUMERO = os.environ.get("ISSUE_NUMBER", "")
REPO = os.environ.get("REPO_SLUG") or slug_do_repo()
CORPO_COMENTARIO = os.environ.get("ISSUE_COMMENT_BODY", "")
TEMPLATE_URL = os.environ.get(
    "TEMPLATE_URL", "https://github.com/endersonmenezes/exam-escola-ti.git")

AJUDA = (
    "**Comandos disponíveis** (comente nesta issue):\n"
    "- `/track <nome>` — seleciona a prova (ex.: `/track dummy-exam`) e já "
    "**aplica automaticamente** no seu repo\n"
    "- `/auto-correcao` — roda a correção completa (trampas + testes "
    "públicos + nota). **Obrigatório ao menos 1x antes de fechar a issue.**\n"
    "- `/ajuda` ou `--help` — mostra esta lista\n"
    "\n"
    "**Ciclo:** preencha `ALUNO.md` → `/track` → desenvolva (commits "
    "pequenos!) → `/auto-correcao` → feche a issue (gera `teacher.json`).\n"
    "Dicas: pushes não disparam correção — rode o comando quando quiser "
    "feedback. Os parâmetros da sua variante ficam em `variante/params.json` "
    "(gerado na aplicação — você só lê o arquivo, nunca precisa gerá-lo).")

AVISO_APLICAR = (
    "⚠️ O comando `/aplicar` foi **descontinuado** — não é mais necessário: "
    "a prova é aplicada automaticamente no momento em que você comenta "
    "`/track <nome>`. Se o comentário “✅ Prova aplicada” já chegou nesta "
    "issue, não há nada a fazer: os seus parâmetros estão em "
    "`variante/params.json` (fonte única).")


def api(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request("https://api.github.com" + path,
                                 data=data, method=method)
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError:
        return 0, {}


def selecionar_track(lock):
    """Parse de `/track <nome>` na issue: valida contra as candidatas do
    template, comenta o feedback na hora e, se valido, grava .prova/track
    (commit de bot + push — o push dispara o aplicar-prova). Retorna o nome
    escolhido ou None (sem /track ou nome invalido)."""
    status_c, comentarios = api("GET", "/repos/%s/issues/%s/comments?per_page=100"
                                % (REPO_FULL, lock))
    track_escolhida = None
    if status_c == 200 and isinstance(comentarios, list):
        for c in comentarios:
            m = re.search(r"(?im)^\s*/track\s+([\w-]+)", c.get("body", "") or "")
            if m:
                track_escolhida = m.group(1)
    if not track_escolhida:
        return None

    candidatas, nomes = [], [track_escolhida]
    if selecao.fetch_template(TEMPLATE_URL):
        candidatas = selecao.candidatas(selecao.pastas_publicadas("FETCH_HEAD"))
        nomes = selecao.nomes(candidatas)
    if candidatas and track_escolhida not in nomes:
        prova_issue.comentar(
            "⚠️ Track `%s` não encontrada. Disponíveis: %s — comente "
            "`/track <nome>` novamente."
            % (track_escolhida, ", ".join("`%s`" % n for n in nomes)))
        return None

    if track_escolhida == os.path.basename(selecao.DUMMY):
        prova_issue.atualizar_comentario(
            "track-ack",
            "✅ Track `%s` selecionada — colocando você em **modo sandbox** 🏖️ "
            "A prova-teste será aplicada neste repo em instantes (acompanhe "
            "por aqui)." % track_escolhida)
    else:
        prova_issue.atualizar_comentario(
            "track-ack",
            "✅ Track `%s` selecionada — aplicando a prova neste repo em "
            "instantes." % track_escolhida)

    track_path = os.path.join(BASE, ".prova", "track")
    atual = ""
    if os.path.exists(track_path):
        atual = open(track_path, encoding="utf-8").read().strip()
    if atual != track_escolhida:
        os.makedirs(os.path.dirname(track_path), exist_ok=True)
        with open(track_path, "w", encoding="utf-8") as f:
            f.write(track_escolhida + "\n")
        for args in (["config", "user.name", "github-actions[bot]"],
                     ["config", "user.email",
                      "41898282+github-actions[bot]@users.noreply.github.com"],
                     ["pull", "--rebase"],
                     ["add", ".prova/track"],
                     ["commit", "-m",
                      "chore: track selecionada via issue (%s)" % track_escolhida],
                     ["push"]):
            subprocess.run(["git"] + args, cwd=BASE, capture_output=True)
    return track_escolhida


def checar_fontes():
    """FONTES.md: ausente = ❌; presente e identico ao template = ⚠️ (edite);
    presente e editado = ✅."""
    fontes_path = os.path.join(BASE, "FONTES.md")
    if not os.path.exists(fontes_path):
        return "❌ `FONTES.md` ausente — restaure o do template."
    editado = True
    if selecao.fetch_template(TEMPLATE_URL):
        remoto = selecao.git("show", "FETCH_HEAD:FONTES.md").stdout
        if remoto:
            local = open(fontes_path, encoding="utf-8", errors="replace").read()
            editado = local != remoto
    if editado:
        return "✅ `FONTES.md` presente e editado (fontes declaradas ou vazio declarado)"
    return ("⚠️ `FONTES.md` ainda idêntico ao do template — edite: declare as "
            "fontes consultadas OU escreva explicitamente que nada foi "
            "utilizado.")


def checar_entrada():
    """Ponto de entrada da spec (tracks SDD): o aluno declara em
    `.prova/entrada` o caminho relativo do arquivo inicial (ex.: SDD/
    README.md) — a correcao por modelo fixo le o indicado e navega pelos
    links. So e exigido quando o lockfile declara `suites.md.entrada`
    (track.json da track, pos-overlay); retorna None nas demais tracks."""
    cfg_md = track_lock.load(BASE).get("suites", {}).get("md", {})
    if not cfg_md.get("entrada"):
        return None
    entrada_path = os.path.join(BASE, ".prova", "entrada")
    if not os.path.exists(entrada_path):
        return ("❌ `.prova/entrada` ausente — a correção precisa saber por onde "
                "começar a ler a sua especificação: crie o arquivo com o caminho "
                "do arquivo inicial (ex.: `README.md` ou `SDD/README.md`) e "
                "commite.")
    alvo = open(entrada_path, encoding="utf-8", errors="replace").read().strip()
    if not alvo:
        return ("❌ `.prova/entrada` vazio — escreva nele o caminho do arquivo "
                "inicial da sua especificação (ex.: `README.md`).")
    partes = alvo.replace("\\", "/").split("/")
    if alvo.startswith("/") or any(p in ("..", "") for p in partes):
        return ("❌ `.prova/entrada` com caminho inválido (`%s`) — use caminho "
                "relativo dentro do repo, sem `..` (ex.: `SDD/README.md`)." % alvo)
    if not os.path.isfile(os.path.join(BASE, *partes)):
        return ("❌ o arquivo de entrada `%s` não existe — corrija o "
                "`.prova/entrada` para apontar para um arquivo real do seu "
                "repo." % alvo)
    if not alvo.lower().endswith(".md"):
        return ("⚠️ entrada declarada (`%s`) não é Markdown — a correção "
                "recomenda um README índice em `.md`, com links para os demais "
                "arquivos da especificação." % alvo)
    return "✅ ponto de entrada declarado em `.prova/entrada` → `%s`" % alvo


def main():
    if os.environ.get("REPO_FULL", "") == "endersonmenezes/exam-escola-ti":
        print("Repositorio-template — nao e uma prova; no-op.")
        return

    lock = prova_issue.numero()
    if lock is None:
        print("Lock .prova/issue ausente (setup nao rodou?) — no-op.")
        return
    if NUMERO:
        try:
            if int(NUMERO) != lock:
                print("Nao e a issue da prova (evento #%s != lock #%s) — no-op."
                      % (NUMERO, lock))
                return
        except ValueError:
            print("ISSUE_NUMBER invalido (%s) — no-op." % NUMERO)
            return

    identidade, prova = [], []

    # ROTEAMENTO (v3.5): em issue_comment, so responde a /track <nome>,
    # /ajuda|--help ou /aplicar (este último só para avisar da descontinuação)
    # — outros comentarios (/auto-correcao, conversa) sao SILENCIO TOTAL (a
    # auto-correcao responde pela propria run; o bug era responder a qualquer
    # comentario repetindo a selecao do .prova/track).
    corpo = CORPO_COMENTARIO.strip()
    eh_aplicar = False
    if corpo:
        m_track = re.match(r"(?i)^\s*/track\s+\S+", corpo)
        eh_ajuda = "/ajuda" in corpo.lower() or "--help" in corpo.lower()
        eh_aplicar = bool(re.match(r"(?i)^\s*/aplicar\b", corpo))
        if not m_track and not eh_ajuda and not eh_aplicar:
            print("Comentario sem comando atendido pelo preparar — silencio total.")
            return

    # 0) Selecao de track (issueops): feedback imediato + aplicacao em cadeia
    escolhida = selecionar_track(lock)
    if escolhida:
        prova.append("✅ track `%s` gravada em `.prova/track` — a aplicação foi "
                     "disparada (acompanhe por aqui)." % escolhida)

    if "/ajuda" in corpo.lower() or "--help" in corpo.lower():
        prova_issue.comentar(AJUDA)
        print("Resposta de /ajuda postada na issue #%s." % lock)
        return

    if eh_aplicar:
        prova_issue.atualizar_comentario("aplicar-deprecado", AVISO_APLICAR)
        print("Aviso de descontinuacao do /aplicar postado na issue #%s." % lock)

    # 1) ALUNO.md com RA — Fase 1 (Identidade)
    aluno_path = os.path.join(BASE, "ALUNO.md")
    if not os.path.exists(aluno_path):
        identidade.append("❌ `ALUNO.md` ausente — algo falhou no setup; comente aqui para o professor ver.")
    else:
        texto = open(aluno_path, encoding="utf-8", errors="replace").read()
        if re.search(r"RA\s*[:：]?\s*[0-9]{5,}", texto) and "PREENCHER" not in texto:
            identidade.append("✅ `ALUNO.md` com RA válido")
        else:
            identidade.append("❌ `ALUNO.md` sem RA válido — preencha e commite.")

    # 2) identidade canonica — Fase 1
    id_path = os.path.join(BASE, ".prova", "id")
    if os.path.exists(id_path) and open(id_path, encoding="utf-8").read().strip() == REPO:
        identidade.append("✅ identidade da prova confere com o repositório")
    else:
        identidade.append("❌ `.prova/id` ausente ou divergente — rode `python scripts/variante.py`.")

    # 3) FONTES.md presente E editado em relacao ao template — Fase 2
    prova.append(checar_fontes())

    # 4) variante — Fase 2. v3.7: valida SOMENTE quando a aplicacao de fato
    #    aconteceu (marcador .prova/exam-dir ou contrato.json na raiz — ambos
    #    entram no commit de aplicacao). Antes dela, o fallback de
    #    pasta_do_ano() encontra exams/<ano> herdada da GERACAO do repo (o
    #    template publicado) e o ❌ antigo ("rode scripts/variante.py") ficava
    #    visivel para o aluno — caso real recorrente na turma de 2026.
    aplicada = (os.path.exists(os.path.join(BASE, ".prova", "exam-dir"))
                or os.path.exists(os.path.join(BASE, "contrato.json")))
    if not aplicada:
        prova.append("⏳ prova ainda não aplicada — sua variante será gerada em "
                     "`variante/params.json` no commit de aplicação (nada a "
                     "fazer agora)")
    else:
        pasta = pasta_do_ano(BASE)
        esperado = variante(REPO)
        params_path = os.path.join(BASE, "variante", "params.json")
        if os.path.exists(params_path):
            gravado = json.load(open(params_path, encoding="utf-8"))
            diffs = [k for k in esperado if gravado.get(k) != esperado[k]]
            prova.append("✅ variante coerente com `variante/params.json` (pasta `%s`)" % pasta if not diffs
                         else "❌ `variante/params.json` diverge em: %s — restaure o arquivo do commit de aplicação." % ", ".join(diffs))
        else:
            prova.append("❌ `variante/params.json` ausente (ele é gerado no commit "
                         "de aplicação) — se você o apagou, rode `python "
                         "scripts/variante.py` localmente e commite o resultado.")

    # 5) ponto de entrada da spec (tracks que declaram suites.md.entrada no
    #    track.json — ex.: SDD). So vale pos-aplicacao: sem track.json na
    #    raiz, track_lock.load devolve lock vazio e a exigencia fica desligada.
    entrada_msg = checar_entrada()
    if entrada_msg:
        prova.append(entrada_msg)

    todas = identidade + prova
    faltam = [l for l in todas if l.startswith("❌")]
    if faltam:
        corpo = ("🔎 **Preparação incompleta**\n\n"
                 "### Fase 1 — Identidade\n\n" + "\n".join(identidade) +
                 "\n\n### Fase 2 — Prova\n\n" + "\n".join(prova) +
                 "\n\nResolva os ❌ e marque os checkboxes de novo; eu revalido. 💪")
    else:
        if pasta:
            proximo = ("Desenvolva e dê push dentro da janela; rode "
                       "`/auto-correcao` quando quiser feedback; **feche esta "
                       "issue ao final** — o sistema gera o `teacher.json` de "
                       "entrega.")
        elif escolhida:
            proximo = ("Sua seleção foi registrada — a prova será aplicada em "
                       "instantes (acompanhe por aqui).")
        else:
            proximo = ("Selecione sua prova comentando `/track <nome>` aqui (a "
                       "lista está no comentário de boas-vindas).")
        corpo = ("✅ **Preparação em dia!**\n\n"
                 "### Fase 1 — Identidade\n\n" + "\n".join(identidade) +
                 "\n\n### Fase 2 — Prova\n\n" + "\n".join(prova) +
                 "\n\n### Próximo passo\n\n" + proximo + "\n\nBoa prova! 🚀")

    prova_issue.atualizar_comentario("preparacao", corpo)
    print("Respondido (upsert) na issue #%s (%s)."
          % (lock, "ok" if not faltam else "pendencias"))


if __name__ == "__main__":
    main()
