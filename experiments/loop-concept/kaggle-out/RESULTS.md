# Loop concept vs syntax: results

## Qwen/Qwen3-0.6B

25 tasks; each cell is 1 greedy answer + 4 sampled answers per task (125 programs). 'solved' = at least one of the 5 answers passed.

| language | arm | greedy pass | all answers: pass | syntax fail | wrong output | tasks solved |
|---|---|---|---|---|---|---|
| Python | cold | 56% | 55% | 0% | 45% | 20/25 |
| Python | snippet | 24% | 23% | 1% | 76% | 9/25 |
| Zig 0.17 | cold | 0% | 0% | 100% | 0% | 0/25 |
| Zig 0.17 | snippet | 0% | 0% | 74% | 26% | 0/25 |
| Plink | cold | 0% | 0% | 100% | 0% | 0/25 |
| Plink | snippet | 0% | 0% | 63% | 37% | 0/25 |

Tasks it solves in plain Python (it has the concept): 20/25. Of those, how many it also solves in:

- Zig 0.17 cold: 0/20
- Zig 0.17 snippet: 0/20
- Plink cold: 0/20
- Plink snippet: 0/20

Per task (greedy answer; P pass, S syntax fail, W wrong output):

| task | Python cold | Python snippet | Zig 0.17 cold | Zig 0.17 snippet | Plink cold | Plink snippet |
|---|---|---|---|---|---|---|
| sum100 | P | W | S | S | S | W |
| evens | W | W | S | W | S | W |
| countdown | P | W | S | W | S | W |
| fact10 | P | W | S | S | S | S |
| fib15 | W | W | S | S | S | S |
| squares | P | P | S | S | S | W |
| times7 | W | P | S | W | S | W |
| arrsum | W | W | S | S | S | S |
| arrmax | W | W | S | S | S | S |
| oddcount | W | W | S | S | S | S |
| primes | P | W | S | W | S | S |
| digitsum | P | W | S | S | S | W |
| gcd | P | W | S | W | S | W |
| collatz | W | W | S | S | S | S |
| pow2 | W | W | S | S | S | W |
| reverse | P | P | S | S | S | S |
| fizzbuzz | P | P | S | W | S | S |
| stars | W | W | S | S | S | W |
| mult35 | P | W | S | S | S | W |
| odds | P | W | S | S | S | S |
| running | W | W | S | S | S | S |
| down3 | P | W | S | W | S | W |
| pairs | P | P | S | S | S | S |
| indexed | P | P | S | S | S | S |
| revnum | W | W | S | S | S | W |

## Qwen/Qwen3-1.7B

25 tasks; each cell is 1 greedy answer + 4 sampled answers per task (125 programs). 'solved' = at least one of the 5 answers passed.

| language | arm | greedy pass | all answers: pass | syntax fail | wrong output | tasks solved |
|---|---|---|---|---|---|---|
| Python | cold | 64% | 70% | 0% | 30% | 19/25 |
| Python | snippet | 60% | 63% | 0% | 37% | 18/25 |
| Zig 0.17 | cold | 0% | 0% | 100% | 0% | 0/25 |
| Zig 0.17 | snippet | 12% | 11% | 65% | 24% | 4/25 |
| Plink | cold | 0% | 0% | 100% | 0% | 0/25 |
| Plink | snippet | 12% | 13% | 46% | 42% | 4/25 |

Tasks it solves in plain Python (it has the concept): 19/25. Of those, how many it also solves in:

- Zig 0.17 cold: 0/19
- Zig 0.17 snippet: 3/19
- Plink cold: 0/19
- Plink snippet: 4/19

Per task (greedy answer; P pass, S syntax fail, W wrong output):

| task | Python cold | Python snippet | Zig 0.17 cold | Zig 0.17 snippet | Plink cold | Plink snippet |
|---|---|---|---|---|---|---|
| sum100 | P | W | S | W | S | S |
| evens | P | P | S | S | S | W |
| countdown | P | P | S | W | S | W |
| fact10 | W | W | S | W | S | S |
| fib15 | P | P | S | W | S | S |
| squares | P | P | S | W | S | S |
| times7 | P | P | S | S | S | P |
| arrsum | W | W | S | S | S | W |
| arrmax | W | W | S | W | S | W |
| oddcount | W | W | S | S | S | S |
| primes | P | P | S | S | S | W |
| digitsum | W | W | S | S | S | W |
| gcd | W | P | S | S | S | S |
| collatz | W | W | S | S | S | S |
| pow2 | W | W | S | P | S | W |
| reverse | P | P | S | S | S | S |
| fizzbuzz | P | P | S | S | S | S |
| stars | P | P | S | S | S | W |
| mult35 | P | P | S | S | S | W |
| odds | P | P | S | S | S | P |
| running | P | W | S | S | S | W |
| down3 | P | P | S | P | S | W |
| pairs | P | P | S | P | S | S |
| indexed | P | P | S | S | S | P |
| revnum | W | W | S | S | S | S |

