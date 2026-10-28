# Prova 01 · Track 02 — Debugging (Cadastro de Produtos)

> No momento da aplicação, esta pasta virou o **seu repositório** (enunciado,
> contrato, app quebrada e compose estão na raiz). O esqueleto com os
> workflows de correção continua aqui, por trás.

Você recebe uma aplicação **que não compila / não sobe** (Spring Boot + Maven
no backend, React no frontend, PostgreSQL, tudo orquestrado por Docker
Compose). Há erros deliberados em **3 camadas**: compilação, configuração e
startup/lógica. A prova avalia seu **método de debug**, não sua memória de
sintaxe.

> [!NOTE]
> Os `.md` deste repositório usam *alerts* (`> [!NOTE]`, `> [!WARNING]`…) e
> *footnotes*[^como-usar] de propósito: é o markdown que esperamos ver no seu
> relatório de método (critério E) — *alerts* para hipóteses descartadas e
> *footnotes* para detalhes de diagnóstico.

## O que vale nesta prova

| Critério | Pontos |
| --- | --- |
| A — App funcional ao final (compose sobe tudo + smoke da correção) | 30 |
| B — Erros de compilação corrigidos | 25 |
| C — Erros de configuração corrigidos | 20 |
| D — Erros de startup/lógica corrigidos | 15 |
| E — Método sistemático evidenciado (commits hipótese→correção ou relatório no README do backend) | 10 |
| **Total** | **100** |

> O feedback do CI diz **o status de cada camada** (passou/falhou), nunca
> onde está o erro — diagnosticar é o objeto da prova. O detalhamento por
> erro (proporção dentro de B/C/D) é feito na correção do professor,
> reexecutando o mesmo ambiente.

## Suas ferramentas neste repo

- **Enunciado**: `ENUNCIADO.md` (contrato de "saudável", camadas, restrições)
  — leia **inteiro** antes de mexer em qualquer arquivo
- **Contrato máquina-legível**: `contrato.json` (o mesmo contrato, para a
  correção)
- **Sua variante**: `variante/params.json` (gerada na aplicação; única do seu repo)
- **Nota parcial**: rode `/auto-correcao` na issue "🎯 Prova" — sai no Summary
  do workflow *Auto-correção* **e em comentário na issue**. Obrigatório ao
  menos 1x antes de fechar.
- **Regras e rastreabilidade**: `docs/REGRAS.md` e `FONTES.md`

## Parâmetros da sua variante

Cada repositório tem a sua — derivados do **nome do repo**.[^variante] A
**fonte única** é o arquivo `variante/params.json` (gerado na aplicação) —
leia os seus valores de lá. O comentário de aplicação na issue "🎯 Prova"
só espelha o arquivo:

| Parâmetro | Alvo correto |
| --- | --- |
| `PORTA_PUBLICADA` | Porta no host em que o backend deve ficar acessível |
| `BANCO` | Nome do banco PostgreSQL (compose + backend devem concordar) |
| `ORIGEM_FRONTEND` | Origem permitida no CORS do backend (fixa: `http://localhost:3000`) |

## Regras

- **Janela**: 120 minutos (divulgada como 1h30), contados a partir do commit
  de aplicação ("chore: aplicar prova …", feito pelo bot). O relógio já está
  rodando — dê push antes do fim da janela.
- **Individual. Consulta é permitida — rastreabilidade obrigatória**: qualquer
  site ou IA usados vão para `FONTES.md` (URL/link público + onde aparece no
  entregável). Se não usou nada, declare isso explicitamente lá.
- **IA como agente é proibida** (IA que edita arquivos ou executa comandos no
  seu lugar → nota 0, plágio). IA como consulta, com a conversa pública e
  registrada em `FONTES.md`, é permitida.
- **Não reescreva a aplicação.** Consertar é ajustar o que está quebrado;
  se algo que funcionava deixar de funcionar por sua causa, o critério A vale
  **zero** (regressão). O `Containerfile` de cada serviço deve continuar
  funcionando — a correção reconstrói tudo do zero.
- **Os testes escondidos podem cobrar todo o processo de gestão do SDLC da
  sua entrega** — organização, higiene de código, segredos no repo, linters
  genéricos da linguagem. Entregue como se fosse para produção.
- **Não altere** `scripts/`, `.github/` ou `docs/` (conferido contra o
  template) nem `track.json`/`contrato.json`/`rubrica.json`/`ENUNCIADO.md`
  depois da aplicação (conferido contra o commit de aplicação) — prova zerada.

> [!WARNING]
> O enunciado contém **um exemplo propositalmente inconsistente** com o
> contrato (`exemplo_inconsistente` no `contrato.json`). O contrato manda —
> não copie o exemplo.

> [!TIP]
> Documente o ciclo de debug à medida que avança: um `README.md` no backend
> com uma tabela hipótese → evidência (log) → correção vale ouro no critério
> E — e no dia a dia de trabalho também.

## Agora

1. Leia `ENUNCIADO.md` **inteiro** e confira seus alvos em
   `variante/params.json`.
2. Ciclo esperado: `docker compose up --build` → ler logs → isolar → corrigir
   → subir de novo.
3. **Commits pequenos** com mensagens no padrão `fix: <hipótese> → <correção>`
   — o método pontua (critério E). Pushes **não** disparam correção.
4. Se usou qualquer consulta (site ou IA), preencha `FONTES.md` antes do push
   final.
5. Rode `/auto-correcao` na issue "🎯 Prova" e veja o status de cada camada.
   **Obrigatório ao menos 1x.**
6. **Feche a issue "🎯 Prova"** — isso encerra a prova e gera o
   `teacher.json` de entrega. Fechar sem `/auto-correcao` reabre a issue com
   aviso. Boa prova! 🚀

[^como-usar]: *Footnote* é nota de rodapé: escreva `[^id]` no texto e defina
    `[^id]: texto` em qualquer lugar do arquivo — o GitHub renderiza no rodapé.
[^variante]: A variante é recalculada na correção a partir do nome do seu
    repositório (`scripts/variante.py`; mesma função na suíte). Por isso
    copiar `.env` ou `application.properties` de colega não funciona.

---

## ⚠️ Último aviso — este README é seu

Este arquivo, depois de lido, **é seu**: edite-o e indique o que achar
necessário para a entrega da sua prova — onde está o ponto de entrada da sua
solução, decisões que tomou, o que o corretor deve olhar primeiro. Editar não
pontua, mas evita que algo que você fez passe despercebido na correção.

**Nossos — não edite e não crie arquivos dentro:**

- `tests/public/` — testes da correção. Arquivo novo ou alterado aqui **zera
  a prova** (procedência). Testes próprios são boa prática — crie-os em pasta
  sua (ex.: `tests/app/`, `meus-testes/`), nunca em `tests/public/`.
- `contrato.json`, `rubrica.json`, `track.json`, `ENUNCIADO.md` — intocáveis
  após a aplicação; alteração = zero.
- `scripts/`, `.github/` — motor da prova e workflows; não edite.

**Seus — crie à vontade:** raiz, `src/`, `app/`, `backend/`, `frontend/`,
`tests/<sua-pasta>/`, `meus-testes/`, `docs/` (sem alterar o que já veio,
como `docs/REGRAS.md`). Arquivo novo fora dos caminhos protegidos nunca é
trampa — é trabalho.
