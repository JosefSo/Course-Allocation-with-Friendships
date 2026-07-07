# Пре-регистрация исследования: HBS Social Version B

Статус: проект протокола для ревью руководителем проекта до начала модификации
алгоритма и до запуска новых экспериментов.

Основание: `IMPLEMENTATION_PLAN_V2_RU.md`, `RESEARCH_ANALYSIS_AND_RECOMMENDATIONS_RU.md`,
`PROJECT_OVERVIEW_AND_RESEARCH_IDEAS_RU.md`, `1.MD` и `2.MD`.

## 1. Исследовательская постановка

Исследование сравнивает механизмы распределения мест на курсах, когда полезность
студента зависит от его собственного набора курсов и от совместного назначения с
указанными им друзьями. Основной вопрос: как начальный механизм, правило выбора и
post-processing изменяют efficiency, fairness и распределение выгод при положительных
направленных friendship externalities.

Единица наблюдения в статистическом анализе — один запуск механизма на конкретном
сценарии и seed. Сравнения механизмов выполняются парно на одинаковых сценариях и seeds.

## 2. Модель полезности

Для финального распределения `A` полезность студента `i` от набора курсов `B`:

```text
Course_i(B) = sum Base(i,c), c in B
Friend_i(B; A) = sum FriendWeight(i,f,c), c in B и c in A_f
Combined_i(B; A) = (1-lambda_i) * Course_i(B)
                   + lambda_i * FriendNorm_i(B; A)
```

`FriendNorm` использует тот же фиксированный индивидуальный нормировочный знаменатель,
что и allocation engine. Во время выбора применяется reactive utility по текущему
состоянию. Все evaluation metrics считаются ex-post по финальному `A`.

Представления результатов:

- `course` — только личные предпочтения по курсам;
- `friend` — только реализованные направленные дружеские совпадения;
- `combined` — взвешенная полезность с индивидуальным `lambda_i`.

## 3. Формальные определения envy и EF1

Рассматриваются упорядоченные пары разных студентов `(i,j)`. Во всех определениях
исходная полезность — полезность `i` от собственного набора `A_i` в финальном
распределении. Строгое сравнение использует численную погрешность `epsilon = 1e-9`.

### 3.1. Substitution — основное определение

Студент `i` мысленно получает набор `A_j`; назначения всех остальных студентов,
включая `j`, остаются такими же, как в финальном `A`. Capacity в мысленном сравнении не
проверяется: это оценка зависти, а не допустимый allocation move.

```text
envy_sub(i,j,rep) = max(0, u_i^rep(A_j; A) - u_i^rep(A_i; A))
```

Пара нарушает EF1, если зависть не устраняется ни одним одиночным удалением:

```text
min over c in A_j of
    max(0, u_i^rep(A_j without c; A) - u_i^rep(A_i; A)) > epsilon
```

Если `A_j` пуст, зависти и EF1-нарушения нет.

### 3.2. Swap

Студенты `i` и `j` полностью меняются наборами, остальные назначения фиксированы.
Социальная полезность `i` пересчитывается в контрфактическом распределении, где
`i` получает `A_j`, а `j` получает `A_i`.

Для EF1 перебирается удаление каждого курса из набора, получаемого `i`. Удалённый курс
остаётся неназначенным; `j` получает исходный `A_i`. Берётся минимальный остаточный envy
по всем одиночным удалениям.

### 3.3. Base-only

Классическое аддитивное сравнение только по `Course_i`; friendship utility и `lambda`
игнорируются. Оно применимо только к представлению `course`.

### 3.4. Инвариант при lambda = 0

При `lambda_i = 0` для всех студентов результаты `substitution/combined`,
`swap/combined` и `base-only/course` должны совпадать для каждой пары `(i,j)`. Это
обязательный unit/property test.

### 3.5. Выходные EF1-метрики

Для каждого применимого сочетания definition и representation сохраняются:

- `envy_pair_share` — доля упорядоченных пар с положительным envy;
- `ef1_violation_pair_share` — доля упорядоченных пар с остаточным envy после любого
  одиночного удаления;
- `ef1_violation_student_share` — доля студентов хотя бы с одной нарушающей парой;
- `envy_gap_mean` — средний положительный исходный envy gap среди завидующих пар;
- `envy_gap_max` — максимальный исходный envy gap;
- `ef1_residual_gap_mean` и `ef1_residual_gap_max` — остаточная зависть после лучшего
  одиночного удаления.

Primary EF1-выводы используют `substitution × combined`. Остальные определения и
представления являются exploratory.

## 4. Welfare, overlap и позиционные метрики

- Utilitarian welfare: сумма индивидуальных utilities.
- Egalitarian welfare: минимум индивидуальных utilities.
- Gini: неравенство индивидуальных utilities; меньше — равномернее.
- Канонический Nash: геометрическое среднее строго положительных utilities, эквивалентное
  средней `log(u)` на положительной подвыборке. Доля исключённых нулей всегда выводится
  как `zero_utility_share`; Nash без неё не интерпретируется.
- `nash_zero_safe`: `sum(log(1+u))`; вспомогательная exploratory-метрика.
- Raw overlap: число реализованных направленных троек `(i,f,c)`.
- Possible overlap: число заявленных троек `(i,f,c)`, для которых курс `c` входит в
  финальный набор `i`; это возможности совпадения при фиксированном наборе самого `i`.
- `overlap_rate = realized_overlap / possible_overlap`; при нулевом знаменателе значение
  равно `0`, а такой студент/запуск отдельно отмечается как не имеющий opportunity.
- Rank satisfaction: средняя/медианная позиция назначенного курса, top-1 и top-3 shares.
- Позиция в очереди: абсолютный индекс хода и нормированный индекс `(p-1)/(n-1)`;
  при `n=1` нормированная позиция равна `0`.

Friend opportunity перед ходом — максимальный reactive friend bonus среди доступных
студенту курсов в момент снимка состояния. Actual reactive bonus — бонус выбранного
курса в тот же момент. Ex-post friend utility хранится отдельно и не подменяет эти две
величины.

## 5. Правило несравнимости lambda

Combined utility при разных `lambda` находится на разных нормативных шкалах. Поэтому:

- механизмы нельзя ранжировать по combined welfare между разными `lambda`;
- combined metrics сравниваются только внутри фиксированного `lambda`;
- между уровнями `lambda` сравниваются raw course utility, rank satisfaction, raw
  friend overlap, `overlap_rate` и компонентные fairness-метрики;
- таблицы, CLI и отчёты обязаны явно показывать это предупреждение;
- cross-lambda statistical tests для combined metrics не создаются.

## 6. Гипотезы H1–H8

Канонические H1–H5 взяты из `PROJECT_OVERVIEW_AND_RESEARCH_IDEAS_RU.md`; H6–H8 — из
`RESEARCH_ANALYSIS_AND_RECOMMENDATIONS_RU.md`. Это разрешает расхождение нумерации в
исходных заметках.

- **H1 (E2):** рост `lambda` увеличивает friend overlap/overlap rate, но после некоторого
  порога ухудшает raw base utility и rank satisfaction.
- **H2 (E1b):** `hybrid-global` в среднем даёт более высокий combined utilitarian welfare
  при фиксированном `lambda`, чем соответствующие `swap-global` и `drop-add-global`.
- **H3 (E1b):** personal post-objectives могут снижать global welfare и увеличивать
  combined Gini относительно global-вариантов.
- **H4 (E2):** эффект friendship-aware механизмов зависит от структуры, плотности и
  взаимности сети; между моделями сети основной social outcome — `overlap_rate`.
- **H5 (E2):** существует диапазон `lambda`, в котором social outcome заметно лучше
  `lambda=0`, а потеря base/rank satisfaction и рост inequality ограничены. Это
  исследование frontier, а не заранее заданный допустимый порог.
- **H6 (E3):** с ростом `lambda` преимущество ранней позиции по combined utility
  ослабевает; при плотной взаимной сети поздние позиции получают больше friend
  opportunity. Немонотонность проверяется, но не предполагается как обязательный исход.
- **H7 (E4):** при `lambda>0` recursively balanced picking sequences могут нарушать
  substitution-EF1; частота нарушений зависит от плотности и взаимности сети.
- **H8 (E4):** substitution и swap дают разные EF1-классификации на ненулевой доле
  инстансов и могут менять ранжирование механизмов.

## 7. Эксперименты и заранее выбранные метрики

### E1a — начальные механизмы

Факторы: пять механизмов, `personal/utilitarian`, `none/hybrid-global/hybrid-personal`,
`lambda=0.3`, одна сеть средней плотности, одинаковые 30 seeds.

Primary:

| Метрика | Представление |
| --- | --- |
| Utilitarian welfare | combined |
| Raw base utility, avg position, top-3 | course |
| Raw overlap и overlap_rate | friend |
| Egalitarian welfare | combined |
| Gini | combined |
| EF1 violation pair share | substitution × combined |

Exploratory: Nash с `zero_utility_share`, `nash_zero_safe`, course/friend egalitarian,
base/friend Gini, остальные EF1 definitions и gaps, fill/runtime metrics.

### E1b — post-processing

Основная сетка: `snake × personal × {none + шесть post-режимов}`. Мини-грид:
`snake × utilitarian × {none, hybrid-global, hybrid-personal}`. Те же 30 seeds.

Primary: combined utilitarian welfare, combined Gini, combined egalitarian welfare,
substitution/combined EF1 violation pair share, raw base utility и overlap rate.
Остальные метрики exploratory.

### E2 — price of sociality

`lambda=0.0..1.0` с шагом `0.1`, три модели сети, четыре зафиксированные конфигурации из
плана v2. Primary cross-lambda metrics: raw base utility, avg course position, top-3,
raw overlap внутри модели сети, overlap rate между сетями и base/friend Gini.

Combined welfare, combined egalitarian/Nash/Gini используются только для сравнений
механизмов внутри одного значения `lambda` и не образуют cross-lambda ranking.

### E3 — эффект позиции

Четыре последовательности × `lambda in {0,0.5,1}` × две цели, без post-processing.
Primary: ex-post course/friend/combined utility по децилю нормированной позиции и friend
opportunity перед ходом. Combined-кривые сравниваются только внутри одного `lambda`.
Exploratory: overlap, fill, Gini и различия между раундами.

### E4 — fairness и контрпримеры

Primary: substitution/combined EF1 violation pair share и число устойчивых минимальных
контрпримеров. Exploratory: swap/base-only, envy gaps, knife-edge случаи и различия
ранжирований между definitions.

## 8. Модель поведения и поиск контрпримеров E4

Агент ведёт себя myopic-greedy: на своём ходу выбирает доступный курс с максимальной
текущей reactive utility. Для utilitarian rule используется текущий маржинальный global
welfare. Разрыв равенств фиксирован существующей цепочкой:

```text
utility bucket (9 знаков) -> больший Score -> меньший Position
-> seeded random -> стабильный CourseID
```

EF1 проверяется только ex-post по финальному allocation. Поиск не моделирует
стратегическое поведение, misreporting или look-ahead.

Сетка поиска:

- студентов: 3 и 4;
- курсов: 3 и 4;
- `b`: 1 и 2;
- capacity: 1, 2 и 3, только допустимые случаи `n*b <= sum(capacity)`;
- n=3: полный перебор ограниченного пространства направленных course-specific графов;
- n=4: bounded enumeration/sampling с зафиксированным seed и лимитом в manifest;
- общие и индивидуальные значения `lambda`, включая `0`, умеренные значения и `1`;
- асимметричные связи обязательны.

Контрпример сначала минимизируется по числу студентов, курсов, friendship edges и
ненулевых preference distinctions. Затем он запускается по всем релевантным seeds и
перестановкам первоначального порядка:

- `robust` — нарушение сохраняется без зависимости от случайного tie-break;
- `knife-edge` — нарушение возникает только при части tie-break outcomes.

В основные результаты допускаются только вручную проверенные `robust` примеры.
`knife-edge` публикуются отдельно. Отсутствие примера в ограниченном пространстве
репортится как отрицательный вычислительный результат, а не как доказательство гарантии.

## 9. Статистический анализ

- Для каждого сравнения используются одинаковые seeds.
- Более двух механизмов: Friedman omnibus test.
- После значимого omnibus: парные Wilcoxon signed-rank tests с Holm correction.
- Для пар: rank-biserial effect size и bootstrap 95% confidence interval.
- Уровень значимости: `alpha=0.05`, двусторонние тесты.
- Missing/failed run не заменяется средним: соответствующая парная ячейка исключается и
  число полных пар репортится.
- Primary family корректируется отдельно для каждого эксперимента; exploratory p-values
  помечаются как exploratory.

Consistency/robustness — вторичный анализ: 1000 bootstrap resamples, Spearman correlation
ранжирований, winner agreement и вероятность конфигурации занять первое место. Для E1a
используются 30 paired seeds; split-half не проводится.

## 10. Механизмы и ограничения интерпретации

Основные механизмы: `round-robin`, `snake`, `reverse-repeat`, `last-first-static` и
`simultaneous-priority`. Старое `n-first` остаётся alias `reverse-repeat` без изменения
поведения.

`simultaneous-priority` строит списки всех студентов по одному снимку в начале раунда и
разрешает конфликты одной seeded priority, фиксированной на весь run. Он одновременно
меняет timing информации и способ разрешения конфликтов, поэтому разницу с sequential
draft нельзя интерпретировать как чистый causal effect одновременности.

При `lambda=0` и priority, совпадающей с round-robin order, он должен совпадать с
round-robin allocation. Это обязательный sanity test.

`personal` требует только предпочтения текущего студента. `utilitarian` учитывает
externality на других студентов и предполагает централизованный доступ к чужим
friendship preferences и `lambda`. `social` сохраняется только как deprecated alias
`utilitarian`.

## 11. Воспроизводимость и границы исследования

Каждый run сохраняет config, dataset и их hashes, seed, версию схемы, initial method,
sequence, pick rule, post mode, lambda и network model. Envy definition хранится у
метрики, а не у run, потому что все definitions вычисляются по одному allocation.

До завершения этапа исключены: MMS, стратегические манипуляции, ADCOP, реальные данные,
расписания/prerequisites, general positive theorems и ILP как all-pick architecture.
Существующий ILP остаётся отдельным benchmark для малых инстансов.

Эксперименты E1–E4 не запускаются до утверждения и отдельного коммита этого протокола.
