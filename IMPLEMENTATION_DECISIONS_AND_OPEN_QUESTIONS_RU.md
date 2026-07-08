# Реализация плана Version B: принятые решения, альтернативы и открытые вопросы

Дата аудита: 8 июля 2026 года.

Основание: `IMPLEMENTATION_PLAN_V2_RU.md`, `RESEARCH_PROTOCOL_RU.md` и фактический код
ветки `new-ui-update` до коммита `cb732a0`, а также текущие незакоммиченные изменения
локализации UI.

## 1. Краткий ответ: реализован ли весь план

Нет. План реализован частично.

На текущий момент:

- фаза 0 (протокол) технически создана и была закоммичена до кода метрик;
- фаза 1 (метрики) реализована почти полностью;
- фаза 2 (механизмы) реализована;
- фаза 3 (исследовательская инфраструктура) реализована большей частью, но не полностью;
- фаза 4 (E1a, E1b, E2, E3) не завершена: выполнен только инженерный smoke pilot E1a
  на трёх seeds, непригодный для научных выводов;
- фаза 5 (поиск EF1-контрпримеров и robustness) не реализована;
- фаза 6 (полный исследовательский UI с шестью вкладками) не реализована. При этом
  одиночный UI уже получил часть аналитических графиков раньше предусмотренного планом
  срока.

Текущий автоматический набор содержит 90 тестов; все 90 проходят. Это подтверждает
инженерную согласованность реализованной части, но не означает завершение научной части
плана.

## 2. Матрица выполнения по фазам

### Фаза 0 — пре-регистрация: в основном выполнена, но формально не закрыта

Создан `RESEARCH_PROTOCOL_RU.md`. По истории Git он был закоммичен коммитом `5ab845e`
до коммитов, реализующих fairness metrics, механизмы и research pipeline.

В протоколе зафиксированы:

- три определения EF1;
- primary и exploratory metrics для E1–E4;
- гипотезы H1–H8;
- запрет сравнения combined utility между разными `lambda`;
- модель поведения агента и tie-breaking для E4;
- статистический план;
- ограничения интерпретации `simultaneous-priority`.

Незакрытый процессуальный вопрос: внутри файла всё ещё указан статус «проект протокола
для ревью». В репозитории нет отдельной отметки, что руководитель утвердил именно эту
версию. Следовательно, требование «review, затем эксперименты» формально не подтверждено,
хотя smoke pilot уже был выполнен.

### Фаза 1 — слой метрик: почти выполнена

Реализованы:

- utilitarian, egalitarian, Gini, Jain, Theil и Atkinson metrics;
- канонический Nash с отдельно выводимой долей нулей;
- `nash_zero_safe`;
- substitution, swap и base-only EF1;
- course, friend и combined representations там, где они применимы;
- envy pair share, EF1 violation pair share, EF1 violation student share;
- средний и максимальный envy gap;
- средний и максимальный residual EF1 gap;
- ex-post utility components;
- raw friend overlap, possible overlap и `overlap_rate`;
- обратные aliases старых EF1-метрик для существующего UI.

Проверено тестами:

- политика нулей Nash;
- расхождение substitution и swap при friendship externality;
- совпадение выбранных EF1-представлений при `lambda=0`;
- формула `overlap_rate` на ручном примере.

Не реализовано из требований фазы 1:

- автоматическая проверка согласованности ранжирований механизмов по каноническому Nash
  и `nash_zero_safe` через Spearman correlation;
- отдельный отчёт, который всегда показывает Nash рядом с `zero_utility_share`. Значения
  сохраняются, но общий UI позволяет смотреть их независимо друг от друга;
- более широкие property tests EF1 на множестве случайных инстансов. Сейчас есть
  небольшие ручные unit tests.

### Фаза 2 — механизмы: выполнена

Реализованы четыре последовательности:

- `round-robin`;
- `snake`;
- `reverse-repeat` с alias `n-first`;
- `last-first-static` с alias `last-first`.

Реализован `simultaneous-priority`: один seeded priority сохраняется на весь run, а
рейтинги курсов строятся по замороженному снимку allocation в начале каждого раунда.

Реализованы draft objectives:

- `personal`;
- `utilitarian`;
- `social` оставлен как deprecated alias для `utilitarian`.

Все шесть post-processing modes работают с обеими начальными архитектурами:

- swap-global / swap-personal;
- drop-add-global / drop-add-personal;
- hybrid-global / hybrid-personal.

Есть тесты точных порядков для 3–5 студентов, aliases, frozen rankings, capacity,
quota, отсутствие дублей, воспроизводимость и эквивалентность simultaneous-priority и
round-robin при `lambda=0` на зафиксированном примере.

### Фаза 3 — инфраструктура: выполнена большей частью

Реализованы:

- генераторы legacy-independent, directed Erdős–Rényi, Watts–Strogatz и planted
  communities;
- density, reciprocity, communities, rewiring probability, top-K и seed;
- scenario manifest;
- расширенный pick log;
- versioned JSON research config;
- config hash и dataset hash;
- отдельная research SQLite database;
- flat CSV, aggregate CSV, JSON statistics;
- простые статические HTML reports для Results, Position Effects и Fairness;
- position CSV и SVG;
- отдельный `research_requirements.txt`;
- Friedman, Wilcoxon, Holm adjustment, rank-biserial effect size и bootstrap mean CI;
- end-to-end smoke test research pipeline.

Схема хранения соответствует ключевому решению плана: `envy_definition` хранится у
metric, а не у run. Все определения EF1 считаются по одному финальному allocation.

Частично или не реализовано:

- полноценная migration framework для research SQLite. Таблицы создаются через
  `CREATE TABLE IF NOT EXISTS`, но теста миграции старой схемы на новую нет;
- PNG-графики отсутствуют; position output создаётся в SVG;
- HTML reports представляют собой базовые таблицы, а не законченные научные отчёты и
  heatmaps;
- bootstrap confidence interval сейчас считается для среднего каждого механизма
  отдельно. CI для парной разницы механизмов не реализован;
- код вычисляет post-hoc Wilcoxon comparisons даже если Friedman omnibus незначим.
  План формулирует последовательность «сначала Friedman, затем post-hoc после
  значимого omnibus»;
- предупреждение о lambda-несравнимости есть в research reports/statistics, но ещё не
  является системным ограничением во всех CLI/UI paths;
- поле `friend_opportunity_at_pick` хранит raw reactive friend bonus, тогда как ex-post
  friend utility хранится нормированной. Это требует очень явных labels в анализе;
- одна и та же итоговая ex-post utility студента повторяется в каждой его строке pick
  log. При одинаковом числе picks это безвредно, но при неполных allocation может
  перевзвешивать студентов в позиционном анализе.

### Фаза 4 — основные эксперименты: не завершена

Существует `pilot_e1a_smoke_result.json`:

- 90 runs;
- 30 mechanism cells;
- по 3 paired seeds;
- 11 070 metric rows;
- 2 160 pick events.

В самом результате правильно записано, что это только engineering smoke test и трёх
seeds недостаточно для научных выводов.

Не выполнены как законченные исследования:

- полный E1a на 30 paired seeds;
- E1b и utilitarian mini-grid;
- E2 price-of-sociality;
- E3 position effects как научный эксперимент;
- итоговые таблицы, frontier и интерпретация результатов.

### Фаза 5 — E4 и robustness: не реализована

Пока нет:

- систематического enumerator/search для малых EF1-контрпримеров;
- перебора directed course-specific friendship graphs;
- minimizer контрпримеров;
- robust vs knife-edge classification;
- JSON/CSV/Markdown artifacts принятых контрпримеров;
- replay tests контрпримеров;
- fairness heatmap;
- 1000-resample consistency ranking analysis;
- Spearman ranking stability, winner agreement и probability-of-being-first.

### Фаза 6 — UI: частично и раньше плана

Полного UI из шести вкладок нет. Есть единый single-run dashboard с:

- запуском initial mechanism и post-processing;
- историей запусков;
- сравнением шести post modes;
- utility histogram и Lorenz curve;
- history analytics и welfare/fairness scatter plot;
- таблицей всех metrics.

Это полезное расширение, но оно не заменяет запланированные Experiment Designer,
Fairness Definitions и Counterexamples views.

## 3. Фактическая модель полезности

### 3.1. Course utility

Course utility вычисляется из `Position` в Table 1, а не непосредственно из `Score`:

```text
Base(i,c) = (K - Position(i,c)) / (K - 1),  если K > 1
```

где `K` — общее число курсов. Поэтому позиция 1 получает 1, последняя позиция — 0.

`Score` используется как tie-break, когда utilities равны после округления до 9 знаков:

```text
utility -> больший Score -> меньший Position -> seeded random -> CourseID
```

Это решение сохранило поведение старой ветки, но оно методологически важно: абсолютная
разница Score не влияет на utility, если порядок Position остаётся тем же.

Альтернативы:

- min-max normalization самого Score;
- cardinal utility из Score без Position;
- Borda utility по Position, как сейчас;
- заранее фиксированная шкала, не зависящая от количества курсов.

Вопрос профессорам: являются ли Scores только средством упорядочивания или они должны
быть cardinal utilities?

### 3.2. Friendship utility и нормировка

Если в Table 2 есть Score, friend weights min-max нормируются по всем присутствующим
friendship rows. Если Scores отсутствуют, используется position-based mapping:

```text
FriendWeight(position) = (K_friend + 1 - position) / K_friend
```

Для каждого студента определяется фиксированный знаменатель:

```text
M_i = max по курсам c суммы всех заявленных FriendWeight(i,f,c)
```

Реализованный normalized friend bonus для курса:

```text
FriendNorm_i(c; A) =
  sum FriendWeight(i,f,c) по друзьям f, назначенным на c, / M_i
```

Combined utility студента:

```text
U_i(A_i; A) = sum по c in A_i:
  (1-lambda_i) * Base(i,c) + lambda_i * FriendNorm_i(c; A)
```

Почему выбран фиксированный student-level denominator: он не меняется от текущего
allocation и не даёт студенту автоматическое преимущество только из-за большего числа
заявленных друзей. Он также позволяет сравнивать реактивный бонус одного студента между
курсами.

Альтернативы:

- нормировать отдельно для каждого курса;
- нормировать на число заявленных друзей;
- использовать raw friendship score без нормировки;
- нормировать на максимально достижимый бонус всего bundle, а не одного курса;
- отделить интенсивность связи от ранга друга.

Открытый вопрос: текущий знаменатель — максимум для одного курса, но utility суммируется
по нескольким курсам. Поэтому суммарная friend component студента может быть больше 1.
Нужно подтвердить, что это желаемая шкала.

## 4. Как именно считается EF1

### 4.1. Важное уточнение: единого «EF1 Score» нет

В проекте нет одного универсального числа EF1. Считается семейство показателей для
каждого definition × representation.

Основной показатель исследования:

```text
ef1_violation_pair_share_substitution_combined
```

Текущая крупная карточка UI «students with EF1 violations» показывает другое число:

```text
ef1_violation_student_share_substitution_combined
```

через backward-compatible alias `ef1_violation_share_total`.

Поэтому значение 0% в карточке означает: ни у одного студента нет хотя бы одной
нарушающей пары по substitution × combined. Это не средняя полезность и не «качество
EF1» по шкале 0–100.

### 4.2. Объект подсчёта

Берутся все упорядоченные пары разных студентов `(i,j)`. Их количество:

```text
n * (n - 1)
```

Пара `(i,j)` отличается от `(j,i)`, потому что предпочтения и friendship edges
направленные.

Для каждой пары сначала вычисляется собственная utility студента `i` от `A_i`, затем
utility того же студента `i` от контрфактического набора `A_j`.

```text
envy_gap(i,j) = max(0, u_i(A_j) - u_i(A_i))
```

Используется `epsilon = 1e-9`. Если gap не больше epsilon, envy нет.

### 4.3. Substitution EF1 — основное определение

Студент `i` мысленно получает bundle `A_j`, но назначения остальных студентов остаются
как в финальном allocation. Это counterfactual evaluation, а не допустимый allocation:
capacity в нём не проверяется.

Если `i` завидует `j`, из `A_j` по очереди удаляется каждый один курс `c`. Для каждого
варианта считается остаточная зависть:

```text
r_c = max(0, u_i(A_j без c; A) - u_i(A_i; A))
```

Берётся лучшее для устранения зависти удаление:

```text
residual(i,j) = min по c in A_j r_c
```

Если `residual(i,j) > 1e-9`, пара нарушает EF1. Иначе зависть устранима удалением одного
предмета и EF1 для этой пары выполнено.

### 4.4. Swap EF1

Студенты `i` и `j` полностью меняются bundles. Friendship utility пересчитывается в
этом контрфактическом allocation. При проверке удаления одного курса `i` получает
`A_j без c`, `j` получает исходный `A_i`, а удалённый курс остаётся неназначенным.

Это определение может дать результат, отличный от substitution, потому что перемещение
`j` меняет friendship overlaps.

### 4.5. Base-only EF1

Friendship utility и `lambda` игнорируются. Сравнивается только аддитивная course
utility. Это классическая версия EF1.

### 4.6. Представления

Для substitution и swap считаются:

- `course`;
- `friend`;
- `combined`.

Для base-only считается только `course`.

### 4.7. Выходные показатели и знаменатели

Для каждого сочетания definition × representation:

```text
envy_pair_share = число завидующих упорядоченных пар / n(n-1)

ef1_violation_pair_share = число нарушающих упорядоченных пар / n(n-1)

ef1_violation_student_share =
  число студентов i, имеющих хотя бы одного j с нарушением / n
```

`envy_gap_mean` считается только среди пар с положительной завистью.

`ef1_residual_gap_mean` считается только среди EF1-нарушающих пар. Пары, где удаление
одного курса устранило envy, в это среднее не входят.

Это условные средние. Их нельзя интерпретировать как средний gap по всем парам.

### 4.8. Почему принято именно такое решение

Выбрано стандартное existential EF1 rule: достаточно существования хотя бы одного
удаляемого курса, устраняющего envy. Поэтому код перебирает все одиночные удаления и
берёт минимальный residual gap.

Substitution выбрано primary, потому что оно ближе к обычному вопросу «предпочёл бы i
набор j?», сохраняя фактическое социальное окружение. Swap оставлено exploratory,
поскольку оно отвечает другому вопросу: «предпочёл бы i полный обмен ролями с j?».

### 4.9. Возможные альтернативы EF1

- считать только неупорядоченные пары;
- делить violation count только на число завидующих пар, а не на все `n(n-1)`;
- удалять предмет только из bundle объекта зависти, как сейчас, или разрешать удаление
  из любого связанного bundle;
- проверять feasible counterfactual с capacity constraints;
- использовать ex-ante utility в момент draft вместо ex-post utility;
- фиксировать friendship environment полностью или пересчитывать все externalities;
- считать EFX, где зависть должна исчезать после удаления любого положительно ценного
  предмета, а не хотя бы одного;
- агрегировать EF1 severity в один score, например `1 - violation_pair_share`, но это
  скрывает разницу между prevalence и magnitude.

## 5. Nash, Gini, egalitarian и overlap: принятые решения

### Nash welfare

Канонический Nash реализован как geometric mean строго положительных utilities:

```text
exp(mean(log(u_i) для u_i > 0))
```

Нули исключаются, а их доля сохраняется отдельно как `zero_utility_share`.

Преимущество: logarithm не ломается на нуле, и остаётся геометрическое среднее
положительной части распределения.

Недостаток: механизм с несколькими нулевыми студентами может иметь высокий Nash среди
оставшихся. Поэтому показатель нельзя читать без `zero_utility_share`.

Альтернативы для обсуждения:

- считать Nash равным 0 при наличии хотя бы одного нуля;
- использовать `sum(log(epsilon + u))` с заранее зафиксированным epsilon;
- использовать только `sum(log(1+u))`, понимая его сближение с utilitarian welfare;
- lexicographic reporting: сначала минимизировать zero share, затем сравнивать Nash.

### Gini

Gini считается стандартно по неотрицательным per-student values. Если сумма равна 0,
возвращается 0. Это означает «нет наблюдаемого неравенства», но одновременно все имеют
нулевой outcome; поэтому Gini также нужно читать вместе с welfare level.

### Egalitarian welfare

Это минимум фактически полученной студентом ex-post utility, а не теоретический минимум
или guarantee:

```text
min_i U_i(A_i; A)
```

### Overlap rate

Raw overlap считает направленные реализованные тройки `(i,f,c)`. Possible overlap
считает заявленные тройки, для которых курс `c` входит в итоговый bundle самого `i`.

```text
overlap_rate = realized / possible
```

При нулевом знаменателе возвращается 0, а отсутствие opportunity учитывается отдельной
метрикой. Альтернатива — хранить `NULL/NA`; она статистически честнее отличает «нулевой
успех при наличии возможности» от «возможности не было».

## 6. Решения по механизмам и спорные места

### Personal и utilitarian draft

`personal` максимизирует собственную текущую combined utility выбирающего студента.

`utilitarian` добавляет marginal externality: пользу, которую приход выбирающего на
курс создаёт уже находящимся там студентам, указавшим его другом.

`social` — только старый alias `utilitarian`. Внутри API он нормализуется в
`utilitarian` с `DeprecationWarning`.

### Personal и global post-processing

`global` принимает move, если растёт сумма utilities всех студентов.

`personal` принимает move по gain инициирующего студента. Для personal swap изменения
utility второго участника и followers не входят в objective. Поэтому такой swap может
ухудшить положение holder или global welfare.

Это не техническая ошибка: именно так реализована децентрализованная personal objective.
Но термин «взаимовыгодный swap» для personal mode был бы неточным, потому что явное
согласие и неухудшение второго участника не проверяются.

Альтернативы:

- Pareto swap: оба участника не проигрывают, хотя бы один выигрывает;
- Nash bargaining gain двух участников;
- global gain с individual-rationality constraints;
- разрешение одностороннего обмена как административной оптимизации, но с другим
  названием.

Это один из наиболее важных вопросов для профессоров.

### Simultaneous-priority

Реализован не «истинный одновременный рынок», а детерминированное разрешение
одновременных rankings одной seeded priority. Rankings заморожены на начало раунда,
после чего priority последовательно получает первый ещё доступный вариант.

Это объединяет два эффекта: stale information и priority conflict resolution. Поэтому
разницу с sequential draft нельзя приписывать только одновременности.

## 7. Статистика: что решено и что требует поправки

Приняты paired seeds. Combined utility разделяется по `lambda` перед inferential tests.

Реализованы:

- Friedman для более двух механизмов;
- pairwise Wilcoxon signed-rank;
- Holm-adjusted p-values;
- matched-pairs rank-biserial correlation;
- percentile bootstrap CI среднего.

Нюансы:

1. Post-hoc tests сейчас вычисляются независимо от значимости Friedman. Нужно решить,
   является ли omnibus gate обязательным или Friedman служит только дополнительной
   диагностикой.
2. Bootstrap CI среднего механизма не является CI paired difference. Для сравнительного
   вывода лучше bootstrap-resample paired seed blocks и строить CI разницы.
3. Holm correction сейчас применяется ко всем парам переданной группы. Нужно заранее
   определить отдельные primary families по экспериментам, как записано в протоколе.
4. Consistency ranking analysis пока отсутствует.
5. Обработка failed/missing runs требует отдельной отчётной проверки: SQL берёт
   пересечение seeds, но причина потери пар явно не репортится.

## 8. Главные открытые вопросы профессорам

### EF1 и fairness

1. Подтверждаем ли `substitution × combined` как primary EF1?
2. Должен ли substitution сохранять j на его исходных курсах, создавая мысленный дубль
   bundle, или нужен feasible transfer?
3. Для swap EF1 правильно ли оставлять удалённый курс неназначенным?
4. Доля нарушающих пар должна делиться на все `n(n-1)` или только на завидующие пары?
5. Нужны ли оба prevalence indicators: pair share и student share? Какой из них должен
   быть главным в UI и статье?
6. Нужна ли EFX или другая fairness notion при externalities?
7. Следует ли residual gap нормировать, чтобы сравнивать datasets разного размера?

### Utility

8. Table 1 Score — cardinal utility или только tie-break после Position?
9. Подтверждается ли student-level friend normalization через максимум одного курса?
10. Допустимо ли, что суммарная friend utility bundle может превышать 1?
11. При отсутствии possible overlap должен `overlap_rate` быть 0 или NA?
12. Какую политику нулей Nash считать основной: исключение нулей + отдельная доля,
    Nash=0, epsilon или lexicographic reporting?

### Механизмы

13. Соответствует ли `simultaneous-priority` исходному смыслу all-pick?
14. Должна ли priority быть общей на весь run или новой в каждом раунде?
15. Допустим ли personal swap, полезный только инициатору, или требуется согласие второго
    студента?
16. Должен ли utilitarian draft учитывать только уже реализуемую externality, как сейчас,
    или ожидаемую будущую externality?

### Экспериментальный дизайн

17. Утверждён ли текущий `RESEARCH_PROTOCOL_RU.md` как финальная пре-регистрация?
18. Достаточно ли 30 paired seeds для E1a–E3 и какие power/effect-size thresholds нужны?
19. Должен ли Friedman статистически gate-ить post-hoc tests?
20. Нужен ли paired bootstrap CI разницы вместо отдельных CI средних?
21. Какой bounded search budget принять для n=4 в E4?
22. Что считать robust контрпримером: все seeds, все начальные permutations или заданная
    доля outcomes?
23. Нужен ли MMS checker в текущем этапе или он остаётся отдельной работой?

## 9. Рекомендуемый порядок продолжения без изменения научных решений

1. Получить письменное подтверждение или поправки к вопросам 1–20 и обновить статус
   протокола отдельным коммитом.
2. Исправить только согласованные методологические расхождения: omnibus gating, paired
   bootstrap, NA policy, personal-swap constraints и labels.
3. Запустить полный E1a, затем E1b mini-grid.
4. После проверки E1 перейти к E2 и E3.
5. Реализовать E4 search, minimization, robustness classification и replay artifacts.
6. Только после научной приёмки расширять UI до шести запланированных views.

До ответов профессоров не следует менять определения EF1, normalization, Nash zero
policy или personal post-processing semantics: это уже не косметические правки, а смена
исследовательской модели.
