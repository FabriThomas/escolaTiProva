#!/usr/bin/env python3
"""README do aluno — job universal (roda em TODAS as tracks aplicadas).

Dois sinais, nessa ordem:
  1. ATUALIZOU? comparacao byte a byte com o README do commit de aplicacao
     (mesma tecnica do T5) — idêntico = o aluno nao tocou no README desde
     que a prova foi aplicada. Heuristica de regex sozinha nao serve: o
     proprio enunciado casa os padroes (caso real 2026 — README da
     track-03 nao editado pontuava 5/5).
  2. TEM INSTRUCOES? heuristica de conteudo herdada do antigo
     check_entrega.py (local+rodar E docker/container).

Pontuacao: peso `readme` da rubrica da track quando existir (ex.:
track-03-crud 2026 = 5). Tracks sem esse peso emitem so observacao
(sem chave "pontos" no result — o nota.py mantem fora da tabela).

Penalidade: README idêntico à prova (ou ausente) gera aviso na issue
unica "Prova" (upsert por marcador — o comentario e editado, nao spamma;
quando o aluno corrige, o MESMO comentario vira ✅ na proxima
/auto-correcao).
"""
import json
import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
import prova_issue  # noqa: E402


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=BASE,
                          capture_output=True, text=True)


def peso_readme():
    """Peso do criterio readme na rubrica pos-overlay (0 = track nao pontua)."""
    alvo = os.path.join(os.getcwd(), "rubrica.json")
    for candidato in (alvo, os.path.join(BASE, "rubrica.json")):
        if os.path.exists(candidato):
            try:
                return int(json.load(open(candidato, encoding="utf-8"))
                           ["criterios"].get("readme", 0))
            except Exception:
                pass
    return 0


def main():
    if os.environ.get("REPO_FULL", "") == "endersonmenezes/exam-escola-ti":
        print("Repositorio-template — nao e uma prova; no-op.")
        return

    peso = peso_readme()
    obs, pontos = [], None

    readme_path = os.path.join(BASE, "README.md")
    if not os.path.exists(readme_path):
        atualizado = False
        obs.append("README.md AUSENTE na raiz.")
        if peso:
            pontos = 0
    else:
        # mesmo t0 do T5: ultimo commit de aplicacao do BOT (um commit do
        # aluno com a mesma mensagem nao ancora nada aqui)
        t0 = git("log", "--format=%H", "--author=github-actions",
                 "--grep=aplicar prova", "-1").stdout.strip()
        if not t0:
            obs.append("commit de aplicacao nao encontrado — verificacao de "
                       "README pulada (trampas ja sinaliza esse estado).")
            atualizado = None
        else:
            r = subprocess.run(["git", "diff", "--quiet", t0, "--", "README.md"],
                               cwd=BASE)
            if r.returncode == 0:
                atualizado = False
                obs.append("README.md identico ao do commit de aplicacao — "
                           "ainda com o texto da prova.")
                if peso:
                    pontos = 0
            elif r.returncode == 1:
                atualizado = True
            else:
                atualizado = None
                obs.append("falha ao comparar README.md com o commit de "
                           "aplicacao (rc=%d) — verificacao pulada." % r.returncode)

    if atualizado:
        texto = open(readme_path, encoding="utf-8", errors="replace").read()
        tem_local = (re.search(r"(local|localhost|dev)", texto, re.I)
                     and re.search(r"(rodar|subir|executar|run)", texto, re.I))
        tem_container = re.search(r"(docker|container)", texto, re.I)
        if tem_local and tem_container:
            cobertura = "instrucoes locais e de container"
            if peso:
                pontos = peso
        elif tem_local or tem_container:
            cobertura = "so local ou so container"
            if peso:
                pontos = max(1, peso // 2)
            obs.append("README cobre so local ou so container.")
        else:
            cobertura = "sem instrucoes de subida"
            if peso:
                pontos = 0
            obs.append("README sem instrucoes de subida.")
        if peso:
            obs.append("README atualizado (%s)." % cobertura)

    # aviso na issue (upsert) — penalidade ou resolucao, no MESMO comentario
    if atualizado is not None and prova_issue.TOKEN and prova_issue.REPO_FULL:
        if atualizado:
            corpo = ("## ✅ README.md atualizado\n\n"
                     "O texto da prova foi substituído por instruções sobre o "
                     "seu trabalho. Bom caminho — segue o jogo.")
            if peso and pontos is not None:
                corpo += ("\n\nCritério README: **%d/%d**." % (pontos, peso))
        else:
            corpo = ("## ⚠️ README.md ainda com o texto da prova\n\n"
                     "Seu README precisa conter instruções sobre o **trabalho "
                     "realizado** — como rodar/subir a sua solução, decisões "
                     "que tomou e o que o corretor deve olhar primeiro — "
                     "**não o enunciado da prova**. Edite o `README.md` e rode "
                     "`/auto-correcao` de novo: este aviso vira ✅ quando o "
                     "README estiver atualizado.")
            if peso:
                corpo += ("\n\nEnquanto estiver com o texto da prova, o "
                          "critério README fica em **0/%d**." % peso)
        try:
            prova_issue.atualizar_comentario("readme-penalidade", corpo)
        except Exception as e:  # issue e feedback, nunca derruba o CI
            obs.append("aviso de README na issue falhou (%s)." % e)

    resultado = {"job": "readme", "obs": obs}
    if peso and pontos is not None:
        resultado.update({"criterio": "README (instruções)",
                          "pontos": pontos, "max": peso})
    with open(os.path.join(BASE, "result-readme.json"), "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
