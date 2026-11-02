# Problem: Subarrays With Sum K

You are given an array of N integers (they may be negative) and an integer K.
Count the number of non-empty contiguous subarrays whose elements sum to exactly K.

## Input
The first line contains N and K (1 ≤ N ≤ 200000, −10^9 ≤ K ≤ 10^9).
The second line contains N integers a_1 … a_N (−10^4 ≤ a_i ≤ 10^4).

## Output
One integer: the number of subarrays with sum K.

## Constraints
N up to 200000, so the solution must run in O(N) or O(N log N) time.

## Examples
Input:
3 2
1 1 1
Output: 2

Input:
5 0
1 -1 1 -1 0
Output: 7

Write the program as solution.py reading stdin and printing the answer.
