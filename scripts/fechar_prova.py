#!/usr/bin/env python3
"""Fechamento da issue da prova -> teacher.json (handshake com o repo teacher).

Gatilho: issues closed. So age se a issue fechada for a do lock
(`.prova/issue` — ver scripts/prova_issue.py); issue de organizacao do aluno
-> no-op. Gera `teacher.json` (schema 1) na RAIZ, com commit do bot + push,
comenta a confirmacao na propria issue (comentario funciona em issue fechada)
e ainda escreve o JSON no Step Summary.

Se a prova nunca foi aplicada, gera o arquivo do mesmo jeito, com
`"aplicada": false` + motivo — fechar sem aplicar e caso real.

`aluno` traz login (dono do repo), RA e **nome** — o nome sai do campo
`Nome:` de `ALUNO.md` (fallback: nome público da conta GitHub via API),
para agilitar o lancamento de notas no sistema academico.

GATE (v3.4): o fechamento exige que a auto-correção tenha rodado ao menos 1x
— o GitHub não permite vetar o fechamento de issue, entao, se o marcador
`<!-- nota-parcial -->` (upsert do nota.py) NÃO existir nos comentarios da
issue, este workflow REABRE a issue com aviso e NAO gera o teacher.json.
Quando presente, o teacher.json ganha `"auto_correcao"` com o flag e a
ultima nota parseada do comentario.

DRY_RUN=1 gera o arquivo local sem commit/push/comentario e sem gate (sem
API) — para teste.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
from variante import pasta_do_ano  # noqa: E402
import prova_issue  # noqa: E402
import fontes  # noqa: E402

TOKEN = os.environ.get("GH_TOKEN", "")
REPO_FULL = os.environ.get("REPO_FULL", "")
REPO = os.environ.get("REPO_SLUG") or os.path.basename(BASE)
ISSUE_NUMBER = os.environ.get("ISSUE_NUMBER", "")
ISSUE_CLOSED_AT = os.environ.get("ISSUE_CLOSED_AT", "")
OWNER = os.environ.get("REPO_OWNER", "")
DRY_RUN = os.environ.get("DRY_RUN", "") == "1"


def sh(*args):
    return subprocess.run(list(args), capture_output=True, text=True,
                          cwd=BASE).stdout


def eh_bot(linha):
    alvo = linha.lower()
    return any(m in alvo for m in ("github-actions", "[bot]",
                                   "noreply@github", "dependabot"))


def iso_agora():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def main():
    if REPO_FULL == "endersonmenezes/exam-escola-ti":
        print("Repositorio-template — nao e uma prova; no-op.")
        return

    lock = prova_issue.numero()
    if not lock or not ISSUE_NUMBER:
        print("Sem lock (.prova/issue) ou sem ISSUE_NUMBER — no-op.")
        return
    try:
        if int(ISSUE_NUMBER) != lock:
            print("Issue fechada (#%s) nao e a da prova (lock #%s) — no-op."
                  % (ISSUE_NUMBER, lock))
            return
    except ValueError:
        print("ISSUE_NUMBER invalido (%s) — no-op." % ISSUE_NUMBER)
        return

    gerado_em = iso_agora()

    # ---- GATE: /auto-correcao ao menos 1x (marcador <!-- nota-parcial -->)
    # na issue. Ausente -> reabre com aviso e NAO gera teacher.json.
    auto_correcao = {"executada": True, "nota_ultima": None}
    if not DRY_RUN and TOKEN and REPO_FULL:
        marcador = "<!-- nota-parcial -->"
        achou = False
        pagina = 1
        while True:
            status, comentarios = prova_issue._api(
                "GET", "/repos/%s/issues/%s/comments?per_page=100&page=%d"
                % (REPO_FULL, lock, pagina))
            if status != 200 or not isinstance(comentarios, list) or not comentarios:
                break
            for c in comentarios:
                corpo_c = c.get("body") or ""
                if corpo_c.startswith(marcador):
                    achou = True
                    m_nota = re.search(r"\*\*Nota parcial:\*\*\s*(\d+)", corpo_c)
                    if m_nota:
                        auto_correcao["nota_ultima"] = int(m_nota.group(1))
            if len(comentarios) < 100:
                break
            pagina += 1
        auto_correcao["executada"] = achou
        if not achou:
            prova_issue.comentar(
                "⚠️ Você ainda não rodou a correção. Comente `/auto-correcao` "
                "nesta issue, aguarde a nota e feche novamente.")
            prova_issue._api("PATCH", "/repos/%s/issues/%s" % (REPO_FULL, lock),
                             {"state": "open"})
            print("Sem /auto-correcao — issue #%d reaberta com aviso; "
                  "teacher.json NAO gerado." % lock)
            summary = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary:
                with open(summary, "a", encoding="utf-8") as f:
                    f.write("## Fechamento bloqueado\n\nO aluno fechou a issue "
                            "sem rodar `/auto-correcao`. A issue foi **reaberta** "
                            "com um aviso; o `teacher.json` só será gerado após "
                            "a primeira correção.\n")
            return

    # ---- prova aplicada? ----
    pasta = pasta_do_ano(BASE)
    track = None
    track_path = os.path.join(BASE, "track.json")
    if os.path.exists(track_path):
        try:
            track = json.load(open(track_path, encoding="utf-8")).get("track")
        except ValueError:
            pass
    t0 = sh("git", "log", "--grep=aplicar prova", "--author=github-actions",
            "--format=%ad", "--date=iso-strict", "-1").strip()
    aplicada = bool(pasta and t0)
    motivo = None
    if not aplicada:
        motivo = ("prova nunca aplicada neste repositorio (sem pasta do ano "
                  "ou sem commit 'aplicar prova')")

    # ---- aluno ----
    ra = None
    nome = None
    aluno_path = os.path.join(BASE, "ALUNO.md")
    if os.path.exists(aluno_path):
        texto_aluno = open(aluno_path, encoding="utf-8", errors="replace").read()
        m = re.search(r"RA\s*[:：]?\s*([0-9]{5,})", texto_aluno)
        if m:
            ra = m.group(1)
        m_nome = re.search(r"^\s*Nome\s*[:：][ \t]*(.+?)[ \t]*$",
                           texto_aluno, re.MULTILINE | re.IGNORECASE)
        if m_nome:
            candidato = m_nome.group(1).strip()
            if candidato and "PREENCHER" not in candidato.upper():
                nome = candidato
    if not nome and not DRY_RUN and TOKEN and OWNER:
        status, usuario = prova_issue._api("GET", "/users/%s" % OWNER)
        if status == 200 and usuario.get("name"):
            nome = usuario["name"].strip() or None

    # ---- variante ----
    variante_d = None
    params_path = os.path.join(BASE, "variante", "params.json")
    if os.path.exists(params_path):
        try:
            variante_d = json.load(open(params_path, encoding="utf-8"))
        except ValueError:
            pass

    # ---- ponto de entrada da spec (SDD) — campo opcional no schema 1 ----
    entrada = None
    entrada_path = os.path.join(BASE, ".prova", "entrada")
    if os.path.exists(entrada_path):
        entrada = (open(entrada_path, encoding="utf-8", errors="replace")
                   .read().strip() or None)

    # ---- janela + commits (bot nao conta) ----
    minutos = 120
    rubrica_path = os.path.join(BASE, "rubrica.json")
    if os.path.exists(rubrica_path):
        try:
            minutos = int(json.load(open(rubrica_path, encoding="utf-8"))
                          .get("janela_minutos", 120))
        except Exception:
            pass
    log = sh("git", "log", "--format=%an|%ad", "--date=iso-strict")
    todos = [l for l in log.splitlines() if l.strip()]
    commits_aluno = [l for l in todos if not eh_bot(l)]
    datas = [l.split("|")[1] for l in commits_aluno if "|" in l]
    ultimo_push = datas[0] if datas else None
    primeiro = datas[-1] if datas else None
    autores = sorted({l.split("|")[0] for l in commits_aluno if "|" in l})
    fora = pre_aplicacao = pre_t0_pos_setup = 0
    # v3.8: o marco da "fase de preparacao" e o SETUP do repo (bot), nao o
    # commit de aplicacao — na turma 2026 os alunos comecavam a prova no
    # inicio da aula e o /track+aplicacao acontecia minutos depois; commits
    # entre o setup e o t0 sao trabalho valido, nao "preparacao". Sem commit
    # de setup (repo legado/clonado na mao), cai no comportamento antigo
    # (tudo antes do t0 conta como pre_aplicacao).
    ts = sh("git", "log", "--format=%ad", "--date=iso-strict",
            "--grep=setup inicial da prova", "--author=github-actions",
            "-1").strip()
    if t0:
        try:
            t0dt = datetime.fromisoformat(t0)
            fim = t0dt + timedelta(minutes=minutos)
            dts = [datetime.fromisoformat(d) for d in datas]
            fora = sum(1 for d in dts if d > fim)
            if ts:
                tsdt = datetime.fromisoformat(ts)
                pre_aplicacao = sum(1 for d in dts if d < tsdt)
                pre_t0_pos_setup = sum(1 for d in dts if tsdt <= d <= t0dt)
            else:
                pre_aplicacao = sum(1 for d in dts if d < t0dt)
        except ValueError:
            fora = 0

    # ---- nota parcial (só existe na raiz se alguem a colocou; gitignored) ----
    valor, criterios = None, {}
    nota_path = os.path.join(BASE, "nota.json")
    if os.path.exists(nota_path):
        try:
            nd = json.load(open(nota_path, encoding="utf-8"))
            valor = nd.get("nota")
            criterios = {c.get("criterio", c.get("job", "?")): c.get("pontos", 0)
                         for c in nd.get("criterios", [])}
        except ValueError:
            pass
    if valor is None:
        import glob
        for path in sorted(glob.glob(os.path.join(BASE, "result-*.json"))):
            try:
                rd = json.load(open(path, encoding="utf-8"))
            except ValueError:
                continue
            if "pontos" in rd:
                criterios[rd.get("criterio", rd.get("job", "?"))] = rd.get("pontos", 0)
                valor = (valor or 0) + rd.get("pontos", 0)
            for c in rd.get("criterios", []):
                criterios[c.get("criterio", "?")] = c.get("pontos", 0)
                valor = (valor or 0) + c.get("pontos", 0)

    # ---- fontes (mesma regra do teste publico test_05 — scripts/fontes.py):
    # so contam URLs em linha de TABELA NUMERADA, deduplicadas; texto corrido
    # e exemplos (ex.: https://docs.oracle.com do template) NAO contam.
    f = fontes.analizar(os.path.join(BASE, "FONTES.md"))
    fontes_d = {"presente": f["presente"], "declarou_vazio": f["declarou_vazio"],
                "links": len(f["links"])}

    teacher = {
        "schema": 1,
        "repo": REPO,
        "repo_url": "https://github.com/" + REPO_FULL if REPO_FULL else None,
        "exam_dir": pasta,
        "track": track,
        "issue": lock,
        "issue_url": ("https://github.com/%s/issues/%d" % (REPO_FULL, lock)
                      if REPO_FULL else None),
        "gerado_em": gerado_em,
        "fechada_em": ISSUE_CLOSED_AT or gerado_em,
        "aplicada": aplicada,
        "motivo": motivo,
        "aluno": {"login": OWNER or None, "ra": ra, "nome": nome},
        "variante": variante_d,
        "entrada": entrada,
        "janela": {"minutos": minutos, "t0": t0 or None, "ultimo_push": ultimo_push},
        "commits": {"total": len(commits_aluno), "autores": autores,
                    "primeiro": primeiro, "ultimo": ultimo_push,
                    "fora_da_janela": fora,
                    "pre_aplicacao": pre_aplicacao,
                    "pre_t0_pos_setup": pre_t0_pos_setup},
        "nota_parcial": {"valor": valor, "criterios": criterios},
        "auto_correcao": auto_correcao,
        "fontes": fontes_d,
    }

    with open(os.path.join(BASE, "teacher.json"), "w", encoding="utf-8") as f:
        json.dump(teacher, f, ensure_ascii=False, indent=2)
    print(json.dumps(teacher, ensure_ascii=False, indent=2))

    if DRY_RUN:
        print("DRY_RUN — teacher.json gerado local; sem commit/push/comentario.")
        return

    # commit do bot + push
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"],
                   cwd=BASE, capture_output=True)
    subprocess.run(["git", "config", "user.email",
                    "41898282+github-actions[bot]@users.noreply.github.com"],
                   cwd=BASE, capture_output=True)
    subprocess.run(["git", "add", "teacher.json"], cwd=BASE, capture_output=True)
    subprocess.run(["git", "commit", "-m",
                    "chore: fechar prova (teacher.json)"], cwd=BASE,
                   capture_output=True)
    subprocess.run(["git", "pull", "--rebase"], cwd=BASE, capture_output=True)
    r = subprocess.run(["git", "push"], cwd=BASE, capture_output=True, text=True)
    if r.returncode != 0:
        print("push do teacher.json falhou:", r.stderr.strip())

    prova_issue.comentar(
        "🏁 **Prova encerrada.** `teacher.json` (schema 1) gerado e commitado "
        "neste repositorio — ele e o handshake de entrega para a correção. "
        "Obrigado!")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## teacher.json\n\n```json\n" +
                    json.dumps(teacher, ensure_ascii=False, indent=2) +
                    "\n```\n")


if __name__ == "__main__":
    main()
