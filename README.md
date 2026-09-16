# Curriculum Pipeline

A Claude Code skill that drafts course modules, and a deterministic validator
that decides whether they ship.

The model drafts. Code decides. Nothing half valid is written.

```bash
pip install -r requirements.txt
python -m pytest tests/ -q          # 23 tests, the validator's own suite
python -m pipeline.cli check modules
python -m pipeline.cli render modules
```

## The idea

You cannot guarantee that a language model produces valid output every time.
You can guarantee that invalid output never leaves the pipeline. The
guarantee lives in the gate, not in the model.

The largest single reduction in failure happens before any validation runs:
**the model is never asked for the file.** It returns structured JSON against
a schema; `pipeline/render.py` produces the Markdown and the YAML front
matter from the validated object. The model never touches the syntax, so the
model cannot break the syntax. Unbalanced fences, broken front matter
delimiters and quote characters that change what a YAML value means stop
being possible failures rather than becoming rarer ones.

Rendering is pure. Same object, same bytes, so regenerating a module produces
a diff a human can actually review.

## Four layers

| | Layer | What it decides |
|---|---|---|
| 1 | parse | The front matter is delimited and the YAML parses, using a real parser and never a regular expression |
| 2 | schema | Pydantic v2 with `extra="forbid"`, so an unexpected key is a failure and not a shrug |
| 3 | referential | Across the whole corpus: slugs unique, exercise ids unique, prerequisites resolve, keys not concentrated in one position |
| 4 | executable | Every code solution runs in a subprocess against its own hidden tests, with a timeout |

**Layer 4 is the one that gets skipped**, and it is where the real failures
live. A module can be perfect YAML, satisfy every schema rule, and ship a
solution that does not run.

**Layer 3 catches defects that do not exist in any single file.** The key
concentration check is there because my own published courses shipped 32
multiple choice items with every correct answer at index 0. Clicking the
first option eight times passed the course and issued a certificate. Nobody
complained, and nothing was wrong with any individual item: every one had a
defensible key and plausible distractors. The defect existed only in the
distribution, which is why it survived review and only showed up in the data.

## Validation is not evaluation

Code decides whether the artefact is well formed. It cannot decide whether it
is any good.

Decidable, so automated: fields present, identifiers unique, references
resolve, code runs, keys spread, no option far longer than the rest, key not
sitting in the stem.

Not decidable, so still human: whether a distractor is plausible to somebody
still learning, whether an item measures the skill or the wording, whether
the key is still correct after the library moved a version.

The point of automating the first list is to buy attention for the second.

## Fail closed

On failure the pipeline emits nothing and exits non-zero. `render` refuses to
write anything unless the whole corpus validates first, so one broken module
cannot half publish. The repair loop in the skill is bounded at three
attempts, because an unbounded loop on an impossible request spends money
until somebody notices the bill.

## The validator has its own tests

`tests/test_validation.py` holds one deliberately broken case per rule, and
each asserts on the reason for rejection rather than only on the failure.
Without that, a refactor turns a check into a no-op, every run stays green,
and nothing is being checked.

The suite includes a solution that is schema clean, plausible and wrong (it
forgets the attempt budget) to prove layer 4 catches it, and one that never
terminates to prove the timeout works.

## Layout

```
.claude/skills/course-module/   the skill: how to draft, and the repair loop
pipeline/schema.py              the contract, one definition, three consumers
pipeline/render.py              validated object to bytes, pure and deterministic
pipeline/validate.py            the four layers
pipeline/cli.py                 check and render, both fail closed
modules/*.json                  source of truth
modules/*.md                    build artefacts, never edited by hand
tests/                          the validator's own suite
.github/workflows/ci.yml        the gate
```

The CI job also re-renders and runs `git diff --exit-code`, so a hand edit to
a build artefact fails the merge.

## Análise de itens

O resto deste pipeline julga um item pelo que ele parece. O `pipeline/itemstats.py`
julga-o pelo que ele fez a uma população, e são coisas diferentes: um item pode
estar impecavelmente escrito e continuar a não medir nada.

```python
from pipeline.itemstats import analisar, formatar
print(formatar(analisar(respostas)))   # uma linha por candidato, 1 acertou 0 falhou
```

```
100 candidatos, 8 itens
KR-20: 0.80

item           dificuldade  discrim.
item-1                70%      0.65
item-2                64%      0.72
item-3                45%     -0.89
              discriminacao NEGATIVA (-0.89): os melhores estao a falhar este item, suspeita da chave
item-4                52%      0.82
```

O item 3 tem 45% de acerto. Pela dificuldade sozinha parece o melhor item do
exame. A discriminação diz o contrário: quem tem boa nota no resto está a
falhá-lo, o que quase sempre significa enunciado ambíguo ou chave errada.

**A discriminação é calculada contra a nota total menos o próprio item.** Sem
essa correção cada item correlaciona-se em parte consigo mesmo e a
discriminação aparece inflacionada, sobretudo num exame de oito perguntas onde
o item vale um oitavo da nota. Há um teste só para isso, porque a versão errada
passa todos os outros.

Com as escolhas de cada candidato, e não só o certo ou errado, faz também
análise de distratores: um distrator que ninguém escolhe não está a fazer
trabalho nenhum, e um distrator escolhido por quem tem nota acima da média é
uma segunda resposta defensável disfarçada.

Abaixo de 30 respostas o relatório diz que os números são indicativos em vez de
os apresentar como se decidissem alguma coisa. E onde não há variância devolve
"não calculável" em vez de zero, porque zero significa "não discrimina" e isso
é diferente de "não dá para saber".
