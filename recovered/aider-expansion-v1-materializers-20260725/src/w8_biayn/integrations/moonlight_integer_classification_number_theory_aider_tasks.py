"""Own the 40-root integer-classification and bounded-number-theory expansion."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
CURRICULUM = REPO_ROOT / "docs/aider-synthetic/aider-synthetic-numerical-anchors/GLM47_FLASH_AIDER_POLYGLOT_CPP_INTEGER_CLASSIFICATION_NUMBER_THEORY_CURRICULUM.md"
REMEDY_SPEC = REPO_ROOT / "docs/aider-tasks-spec/aider-numerical-anchors/integer-classification-number-theory-remedy-cycle-06.md"
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
DEFAULT_OUT = EXPANSION_ROOT / "numerical-anchors/integer-classification-number-theory"
EXISTING_ROOTS = (
    REPO_ROOT / ".w8-biayn/data/aider-tasks",
    REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify",
)
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
OWNER = "src/w8_biayn/integrations/moonlight_integer_classification_number_theory_aider_tasks.py"
FAMILY_ID = "integer-classification-number-theory-v1"
DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_or_selection_rules",
    "invalid_and_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
OFFICIAL_HOLDOUTS = frozenset({
    "all-your-base", "allergies", "bank-account", "binary-search-tree",
    "circular-buffer", "clock", "complex-numbers", "crypto-square",
    "diamond", "dnd-character", "gigasecond", "grade-school",
    "kindergarten-garden", "knapsack", "linked-list", "meetup",
    "parallel-letter-frequency", "perfect-numbers", "phone-number",
    "queen-attack", "robot-name", "space-age", "spiral-matrix",
    "sublist", "yacht", "zebra-puzzle",
})
CONTAMINATION_SURFACES = ("prompt", "api", "reference", "tests", "lineage")


class CreatorError(RuntimeError):
    pass


@dataclass(frozen=True)
class Sample:
    args: str
    valid: bool
    member: bool
    value: int
    witness: int


@dataclass(frozen=True)
class Case:
    task_id: str
    title: str
    params: str
    summary: str
    algorithm: str
    boundary: str
    oracle: str
    bad: str
    features: tuple[str, ...]
    body: str
    visible: Sample
    private: tuple[Sample, ...]

    @property
    def snake(self) -> str:
        return self.task_id.replace("-", "_")

    @property
    def namespace(self) -> str:
        return f"number_{self.snake}"

    @property
    def function(self) -> str:
        return f"analyze_{self.snake}"

    @property
    def param_names(self) -> tuple[str, ...]:
        return tuple(part.strip().split()[-1] for part in self.params.split(","))


def S(args: str, valid: bool, member: bool, value: int, witness: int) -> Sample:
    return Sample(args, valid, member, value, witness)


def _cases() -> tuple[Case, ...]:
    # Each body is deliberately emitted alone. Shared helpers are selected only
    # when the root's algorithm needs them; there is no generated policy switch.
    rows = (
        Case("prime-interval-profile", "Prime interval profile", "long long lo, long long hi", "Count primes in a bounded closed interval and return the greatest one.", "segmented trial division over a closed interval", "0 <= lo <= hi <= 1000000 and width <= 10000", "enumerate every candidate and trial divisor", "testing only odd endpoints or treating the interval as half-open", ("prime",), "if(lo<0||hi<lo||hi>1000000||hi-lo>10000)return bad();long long count=0,last=-1;for(long long n=lo;n<=hi;++n){if(is_prime(n)){++count;last=n;}}return ok(count>0,count,last);", S("10,19", True, True, 4, 19), (S("14,16", True, False, 0, -1), S("20,10", False, False, -1, -1))),
        Case("factor-exponent-signature", "Factor exponent signature", "long long n", "Classify a positive integer by total and distinct prime-factor multiplicity.", "monotone prime-exponent extraction", "1 <= n <= 1000000000", "multiply recovered prime powers back to n", "counting distinct factors as total multiplicity", ("factor",), "if(n<1||n>1000000000)return bad();auto f=factors(n);long long omega=0;for(auto q:f)omega+=q.second;return ok(omega>1,omega,f.empty()?1:f.back().first);", S("72", True, True, 5, 3), (S("13", True, False, 1, 13), S("0", False, False, -1, -1))),
        Case("semiprime-factor-pair", "Semiprime factor pair", "long long n", "Recognize exactly two prime factors with multiplicity and return their ordered pair.", "two-factor extraction with primality validation", "4 <= n <= 1000000000", "try every first prime divisor and validate the quotient", "accepting any composite with two distinct divisors", ("factor",), "if(n<4||n>1000000000)return bad();auto f=factors(n);long long total=0;for(auto q:f)total+=q.second;if(total!=2)return ok(false,total,f.empty()?-1:f.back().first);long long a=f.front().first,b=f.size()==1?a:f.back().first;return ok(true,a,b);", S("49", True, True, 7, 7), (S("12", True, False, 3, 3), S("3", False, False, -1, -1))),
        Case("k-almost-prime-membership", "K-almost-prime membership", "long long n, long long k", "Test whether a bounded integer has exactly k prime factors with multiplicity.", "complete multiplicity counter", "2 <= n <= 1000000000 and 1 <= k <= 20", "factor independently then compare the exact exponent sum", "counting only distinct prime factors", ("factor",), "if(n<2||n>1000000000||k<1||k>20)return bad();auto f=factors(n);long long total=0;for(auto q:f)total+=q.second;return ok(total==k,total,f.back().first);", S("60,4", True, True, 4, 5), (S("60,3", True, False, 4, 5), S("1,1", False, False, -1, -1))),
        Case("squarefree-certificate", "Square-free certificate", "long long n", "Classify square-freeness and return the first repeated prime when it fails.", "prime-square divisibility scan", "1 <= n <= 1000000000", "factor exponents and locate the first exponent above one", "checking only divisibility by four", ("factor",), "if(n<1||n>1000000000)return bad();auto f=factors(n);for(auto q:f)if(q.second>1)return ok(false,(long long)f.size(),q.first);return ok(true,(long long)f.size(),f.empty()?1:f.back().first);", S("30", True, True, 3, 5), (S("12", True, False, 2, 2), S("0", False, False, -1, -1))),
        Case("powerful-number-witness", "Powerful number witness", "long long n", "Require every prime exponent to be at least two and report the first violation.", "complete exponent-floor factor classification", "1 <= n <= 1000000000", "recover all exponents and check their minimum", "accepting squares alone or ignoring exponent-one factors", ("factor",), "if(n<1||n>1000000000)return bad();auto f=factors(n);for(auto q:f)if(q.second<2)return ok(false,(long long)f.size(),q.first);return ok(true,(long long)f.size(),f.empty()?1:f.back().first);", S("72", True, True, 2, 3), (S("18", True, False, 2, 2), S("0", False, False, -1, -1))),
        Case("smoothness-bound-profile", "Smoothness bound profile", "long long n, long long bound", "Test B-smoothness and return the largest prime factor.", "largest-prime-factor extraction against an inclusive bound", "2 <= n <= 1000000000 and 2 <= bound <= 1000000000", "factor completely and compare the maximum", "stopping after small factors without checking the residual", ("factor",), "if(n<2||n>1000000000||bound<2||bound>1000000000)return bad();auto f=factors(n);long long largest=f.back().first;return ok(largest<=bound,largest,(long long)f.size());", S("72,3", True, True, 3, 2), (S("70,5", True, False, 7, 3), S("1,3", False, False, -1, -1))),
        Case("roughness-bound-profile", "Roughness bound profile", "long long n, long long bound", "Test B-roughness and return the smallest prime factor.", "smallest-prime-factor search against an inclusive floor", "2 <= n <= 1000000000 and 2 <= bound <= 1000000000", "trial divide from two until the first factor", "using the largest factor instead of the smallest", ("factor",), "if(n<2||n>1000000000||bound<2||bound>1000000000)return bad();auto f=factors(n);long long smallest=f.front().first;return ok(smallest>=bound,smallest,(long long)f.size());", S("77,7", True, True, 7, 2), (S("21,5", True, False, 3, 2), S("1,2", False, False, -1, -1))),
        Case("radical-square-kernel", "Radical and square kernel", "long long n", "Compute the radical and the complementary repeated-factor quotient.", "distinct-prime product with checked quotient", "1 <= n <= 1000000000", "factor then multiply each distinct prime once", "multiplying prime factors with multiplicity", ("factor",), "if(n<1||n>1000000000)return bad();auto f=factors(n);long long rad=1;for(auto q:f)rad*=q.first;return ok(rad==n,rad,n/rad);", S("72", True, False, 6, 12), (S("30", True, True, 30, 1), S("0", False, False, -1, -1))),
        Case("liouville-parity", "Liouville parity", "long long n", "Compute the Liouville sign from total prime-factor multiplicity.", "factor-multiplicity parity accumulation", "1 <= n <= 1000000000", "independent repeated division count", "using distinct-factor parity", ("factor",), "if(n<1||n>1000000000)return bad();auto f=factors(n);long long omega=0;for(auto q:f)omega+=q.second;long long sign=(omega%2==0)?1:-1;return ok(sign==1,sign,omega);", S("12", True, False, -1, 3), (S("18", True, False, -1, 3), S("0", False, False, -1, -1))),
        Case("mobius-squarefree-sign", "Mobius square-free sign", "long long n", "Compute the Möbius value, distinguishing repeated factors from parity.", "square-factor rejection followed by distinct-prime parity", "1 <= n <= 1000000000", "factor exponents and apply the mathematical definition", "returning Liouville parity for non-square-free inputs", ("factor",), "if(n<1||n>1000000000)return bad();auto f=factors(n);for(auto q:f)if(q.second>1)return ok(false,0,q.first);long long mu=(f.size()%2==0)?1:-1;return ok(true,mu,(long long)f.size());", S("30", True, True, -1, 3), (S("12", True, False, 0, 2), S("0", False, False, -1, -1))),
        Case("totient-density-class", "Totient density class", "long long n", "Compute Euler's totient and classify whether more than half the residues are coprime.", "multiplicative totient reduction over distinct primes", "1 <= n <= 1000000000", "count gcd-one residues for bounded private values", "subtracting one per prime rather than a prime fraction", ("factor",), "if(n<1||n>1000000000)return bad();long long phi=n;for(auto q:factors(n))phi=phi/q.first*(q.first-1);return ok(phi>n/2,phi,n-phi);", S("9", True, True, 6, 3), (S("12", True, False, 4, 8), S("0", False, False, -1, -1))),
        Case("carmichael-exponent-bound", "Carmichael exponent bound", "long long n", "Compute the least universal exponent for units modulo n.", "prime-power Carmichael values merged by lcm", "2 <= n <= 1000000", "enumerate units and verify the resulting exponent", "using Euler's totient unchanged", ("factor", "gcd"), "if(n<2||n>1000000)return bad();long long lambda=1;for(auto q:factors(n)){long long p=q.first,e=q.second,term=1;for(long long i=1;i<e;++i)term*=p;term*=p-1;if(p==2&&e>=3)term/=2;lambda=lcmll(lambda,term);}return ok(lambda<n-1,lambda,n/lambda);", S("8", True, True, 2, 4), (S("5", True, False, 4, 1), S("1", False, False, -1, -1))),
        Case("multiplicative-order", "Multiplicative order", "long long a, long long modulus", "Return the least positive exponent taking a coprime residue to one.", "bounded modular orbit with first-return detection", "2 <= modulus <= 100000 and abs(a) <= 1000000000", "multiply residues until first return or totient bound", "returning the modulus or totient without testing minimality", ("gcd",), "if(modulus<2||modulus>100000||a<-1000000000||a>1000000000)return bad();a%=modulus;if(a<0)a+=modulus;long long g=gcdll(a,modulus);if(g!=1)return ok(false,0,g);long long cur=1;for(long long k=1;k<=modulus;++k){cur=(cur*a)%modulus;if(cur==1)return ok(true,k,cur);}return ok(false,0,-1);", S("2,5", True, True, 4, 1), (S("6,9", True, False, 0, 3), S("2,1", False, False, -1, -1))),
        Case("modular-inverse", "Modular inverse", "long long a, long long modulus", "Return the least nonnegative modular inverse when it exists.", "extended-Euclidean inverse normalization", "2 <= modulus <= 1000000000 and abs(a) <= 1000000000", "multiply the returned residue modulo m", "using integer division or accepting non-coprime inputs", ("egcd",), "if(modulus<2||modulus>1000000000||a<-1000000000||a>1000000000)return bad();long long x=0,y=0;long long g=egcd(a,modulus,x,y);if(g!=1&&g!=-1)return ok(false,0,g<0?-g:g);if(g==-1)x=-x;x%=modulus;if(x<0)x+=modulus;return ok(true,x,1);", S("3,11", True, True, 4, 1), (S("6,9", True, False, 0, 3), S("1,1", False, False, -1, -1))),
        Case("linear-congruence-solver", "Linear congruence solver", "long long a, long long b, long long modulus", "Classify ax=b modulo m and return the least solution modulo the reduced modulus.", "gcd reduction plus normalized extended-Euclidean solve", "2 <= modulus <= 1000000000 and abs(a),abs(b) <= 1000000000", "substitute the solution and enumerate one reduced period", "requiring a modular inverse before gcd reduction", ("egcd", "gcd"), "if(modulus<2||modulus>1000000000||a<-1000000000||a>1000000000||b<-1000000000||b>1000000000)return bad();long long g=gcdll(a,modulus);if(b%g!=0)return ok(false,0,g);long long m=modulus/g,x=0,y=0;egcd(a/g,m,x,y);long long r=((b/g)%m*x)%m;if(r<0)r+=m;return ok(true,r,m);", S("6,8,14", True, True, 6, 7), (S("6,5,14", True, False, 0, 2), S("1,1,1", False, False, -1, -1))),
        Case("crt-pair-merge", "CRT pair merge", "long long r1, long long m1, long long r2, long long m2", "Merge two possibly non-coprime congruences into a least residue and lcm modulus.", "compatibility-gated generalized CRT merge", "2 <= m1,m2 <= 1000000 and abs residues <= 1000000000", "enumerate one lcm period for bounded cases", "multiplying moduli and assuming coprimality", ("egcd", "gcd"), "if(m1<2||m2<2||m1>1000000||m2>1000000||r1<-1000000000||r1>1000000000||r2<-1000000000||r2>1000000000)return bad();r1%=m1;if(r1<0)r1+=m1;r2%=m2;if(r2<0)r2+=m2;long long g=gcdll(m1,m2);if((r2-r1)%g!=0)return ok(false,0,g);long long x=0,y=0;egcd(m1/g,m2/g,x,y);long long mod=m1/g*m2;long long t=((r2-r1)/g%(m2/g)*x)%(m2/g);long long r=(r1+m1*t)%mod;if(r<0)r+=mod;return ok(true,r,mod);", S("2,3,3,5", True, True, 8, 15), (S("1,4,3,6", True, True, 9, 12), S("1,4,2,6", True, False, 0, 2))),
        Case("quadratic-residue-witness", "Quadratic residue witness", "long long residue, long long prime", "Find the least nonnegative square root modulo a bounded prime.", "complete least-witness residue scan", "2 <= prime <= 100000, prime must be prime, abs residue <= 1000000000", "enumerate every residue and compare squares", "using Euler's test without returning a checked witness", ("prime",), "if(prime<2||prime>100000||!is_prime(prime)||residue<-1000000000||residue>1000000000)return bad();residue%=prime;if(residue<0)residue+=prime;for(long long x=0;x<prime;++x)if((x*x)%prime==residue)return ok(true,residue,x);return ok(false,residue,-1);", S("10,13", True, True, 10, 6), (S("2,13", True, False, 2, -1), S("1,12", False, False, -1, -1))),
        Case("jacobi-symbol", "Jacobi symbol", "long long a, long long odd_modulus", "Compute the Jacobi symbol through binary reciprocity reductions.", "binary Jacobi reciprocity state machine", "3 <= odd_modulus <= 1000000001 and odd", "factor the modulus and multiply Legendre symbols", "treating the Jacobi symbol as a primality or residue certificate", (), "if(odd_modulus<3||odd_modulus>1000000001||odd_modulus%2==0||a<-1000000000||a>1000000000)return bad();long long n=odd_modulus;a%=n;if(a<0)a+=n;int result=1;while(a!=0){while(a%2==0){a/=2;long long r=n%8;if(r==3||r==5)result=-result;}long long t=a;a=n;n=t;if(a%4==3&&n%4==3)result=-result;a%=n;}return ok(n==1&&result==1,n==1?result:0,n);", S("2,3", True, False, -1, 1), (S("5,11", True, True, 1, 1), S("2,4", False, False, -1, -1))),
        Case("primitive-root-verifier", "Primitive root verifier", "long long generator, long long prime", "Verify a proposed primitive root for a bounded prime modulus and return its order.", "order computation with prime-minus-one factor witnesses", "3 <= prime <= 100000, prime must be prime, 1 <= generator < prime", "enumerate powers until first return", "checking only that the generator is nonzero", ("prime",), "if(prime<3||prime>100000||!is_prime(prime)||generator<1||generator>=prime)return bad();long long cur=1,order=0;do{cur=(cur*generator)%prime;++order;}while(cur!=1&&order<=prime);return ok(order==prime-1,order,prime-1);", S("2,5", True, True, 4, 4), (S("4,5", True, False, 2, 4), S("2,4", False, False, -1, -1))),
        Case("fibonacci-index-membership", "Fibonacci index membership", "long long n", "Return the first Fibonacci index of a bounded nonnegative integer.", "monotone checked Fibonacci recurrence", "0 <= n <= 1000000000", "generate the sequence independently from F0 and F1", "using a floating square test and losing the first index of one", (), "if(n<0||n>1000000000)return bad();if(n==0)return ok(true,0,0);long long a=0,b=1,index=1;while(b<n){long long c=a+b;a=b;b=c;++index;}return ok(b==n,index,b==n?b:a);", S("34", True, True, 9, 34), (S("35", True, False, 10, 34), S("-1", False, False, -1, -1))),
        Case("lucas-index-membership", "Lucas index membership", "long long n", "Return the first Lucas-sequence index of a positive bounded integer.", "two-seed Lucas recurrence with ordered overshoot", "1 <= n <= 1000000000", "generate L0=2,L1=1 without Fibonacci substitution", "starting from Fibonacci seeds", (), "if(n<1||n>1000000000)return bad();if(n==2)return ok(true,0,2);long long a=2,b=1,index=1;while(b<n){long long c=a+b;a=b;b=c;++index;}return ok(b==n,index,b==n?b:a);", S("47", True, True, 8, 47), (S("34", True, False, 8, 29), S("0", False, False, -1, -1))),
        Case("triangular-index-membership", "Triangular index membership", "long long n", "Return the nonnegative index k when n=k(k+1)/2.", "overflow-safe monotone triangular accumulation", "0 <= n <= 1000000000", "sum consecutive integers until reaching n", "using a rounded floating quadratic root", (), "if(n<0||n>1000000000)return bad();long long value=0,k=0;while(value<n){++k;value+=k;}return ok(value==n,k,value);", S("21", True, True, 6, 21), (S("22", True, False, 7, 28), S("-1", False, False, -1, -1))),
        Case("polygonal-index-membership", "Polygonal index membership", "long long n, long long sides", "Classify an integer as s-gonal and return the first positive index.", "bounded polygonal recurrence by growing differences", "1 <= n <= 1000000000 and 3 <= sides <= 12", "evaluate the closed form for every bounded index", "hard-coding triangular and square cases", (), "if(n<1||n>1000000000||sides<3||sides>12)return bad();long long value=1,k=1,delta=sides-1;while(value<n){++k;value+=delta;delta+=sides-2;}return ok(value==n,k,value);", S("22,5", True, True, 4, 22), (S("23,5", True, False, 5, 35), S("1,2", False, False, -1, -1))),
        Case("centered-polygonal-membership", "Centered polygonal membership", "long long n, long long sides", "Classify n as 1+s*k*(k-1)/2 and return its layer number.", "centered-layer recurrence with s-sized ring growth", "1 <= n <= 1000000000 and 3 <= sides <= 12", "add successive ring sizes and compare", "reusing the ordinary polygonal formula", (), "if(n<1||n>1000000000||sides<3||sides>12)return bad();long long value=1,k=1;while(value<n){value+=sides*k;++k;}return ok(value==n,k,value);", S("31,5", True, True, 4, 31), (S("22,5", True, False, 4, 31), S("1,13", False, False, -1, -1))),
        Case("consecutive-sum-profile", "Consecutive sum profile", "long long n", "Count representations of n as at least two consecutive positive integers and return the shortest length.", "length-divisibility scan with positive-start constraint", "1 <= n <= 1000000000", "enumerate every feasible length and reconstruct the start", "allowing zero or negative starting terms", (), "if(n<1||n>1000000000)return bad();long long count=0,shortest=-1;for(long long len=2;len*(len+1)/2<=n;++len){long long rem=n-len*(len-1)/2;if(rem>0&&rem%len==0){++count;if(shortest==-1)shortest=len;}}return ok(count>0,count,shortest);", S("15", True, True, 3, 2), (S("8", True, False, 0, -1), S("0", False, False, -1, -1))),
        Case("happy-cycle-class", "Happy cycle class", "long long n", "Classify the decimal square-digit orbit and report steps to one or first cycle repeat.", "explicit orbit table with repeat detection", "1 <= n <= 1000000000", "track every orbit state until one or repetition", "using a fixed iteration cap as proof of unhappiness", ("digit_power",), "if(n<1||n>1000000000)return bad();std::vector<long long> seen;long long steps=0;while(n!=1){for(long long x:seen)if(x==n)return ok(false,steps,n);seen.push_back(n);n=digit_power_sum(n,10,2);++steps;}return ok(true,steps,1);", S("19", True, True, 4, 1), (S("2", True, False, 9, 4), S("0", False, False, -1, -1))),
        Case("narcissistic-base-class", "Narcissistic base class", "long long n, long long base", "Test whether n equals the sum of its base-b digits raised to the digit count.", "base digit extraction plus checked repeated multiplication", "0 <= n <= 1000000000 and 2 <= base <= 16", "extract digits then recompute each power", "always cubing decimal digits", ("digit_power",), "if(n<0||n>1000000000||base<2||base>16)return bad();long long x=n,count=1;while(x>=base){x/=base;++count;}long long sum=digit_power_sum(n,base,count);return ok(sum==n,sum,count);", S("153,10", True, True, 153, 3), (S("10,2", True, False, 2, 4), S("1,1", False, False, -1, -1))),
        Case("kaprekar-split-witness", "Kaprekar split witness", "long long n, long long base", "Find a nonempty base-b split of n squared whose parts sum to n.", "checked square and radix-power split enumeration", "1 <= n <= 1000000 and 2 <= base <= 16", "try every digit split with a nonzero right part", "allowing an empty or zero right part", (), "if(n<1||n>1000000||base<2||base>16)return bad();long long square=n*n,power=base;for(long long digits=1;power<=square*base&&power>0;power*=base,++digits){long long right=square%power,left=square/power;if(right>0&&left+right==n)return ok(true,digits,right);if(power>1000000000000000000LL/base)break;}return ok(false,0,-1);", S("45,10", True, True, 2, 25), (S("10,10", True, False, 0, -1), S("0,10", False, False, -1, -1))),
        Case("automorphic-suffix-class", "Automorphic suffix class", "long long n, long long base", "Test whether n squared ends with all base-b digits of n.", "digit-width modulus construction with checked square", "0 <= n <= 1000000000 and 2 <= base <= 16", "construct base^digits and compare the exact suffix", "checking only the last decimal digit", (), "if(n<0||n>1000000000||base<2||base>16)return bad();long long modulus=base,x=n;while(x>=base){if(modulus>1000000000000000000LL/base)return bad();modulus*=base;x/=base;}long long square=n*n;return ok(square%modulus==n,modulus,square%modulus);", S("25,10", True, True, 100, 25), (S("26,10", True, False, 100, 76), S("1,1", False, False, -1, -1))),
        Case("harshad-quotient", "Harshad quotient", "long long n, long long base", "Classify divisibility by the base-b digit sum and return the quotient.", "radix digit-sum accumulation with zero guard", "1 <= n <= 1000000000 and 2 <= base <= 16", "extract all digits and multiply quotient back", "summing decimal digits regardless of base", ("digit_sum",), "if(n<1||n>1000000000||base<2||base>16)return bad();long long sum=digit_sum(n,base);return ok(n%sum==0,sum,n%sum==0?n/sum:n%sum);", S("18,10", True, True, 9, 2), (S("19,10", True, False, 10, 9), S("1,1", False, False, -1, -1))),
        Case("smith-composite-class", "Smith composite class", "long long n", "For a composite, compare decimal digit sum with prime-factor digit sums including multiplicity.", "multiplicity-preserving factor digit-sum comparison", "4 <= n <= 1000000000", "factor fully and independently sum every repeated prime", "accepting primes or counting each prime only once", ("factor", "digit_sum", "prime"), "if(n<4||n>1000000000)return bad();if(is_prime(n))return ok(false,digit_sum(n,10),n);auto f=factors(n);long long sum=0;for(auto q:f)for(long long i=0;i<q.second;++i)sum+=digit_sum(q.first,10);long long own=digit_sum(n,10);return ok(sum==own,own,sum);", S("22", True, True, 4, 4), (S("13", True, False, 4, 13), S("3", False, False, -1, -1))),
        Case("emirp-reversal-class", "Emirp reversal class", "long long n", "Require n and its distinct decimal reversal to both be prime.", "checked decimal reversal followed by two primality proofs", "10 <= n <= 1000000000", "reverse digits explicitly and trial-divide both values", "accepting palindromic primes", ("prime", "reverse"), "if(n<10||n>1000000000)return bad();long long reversed=reverse_base(n,10);bool member=is_prime(n)&&reversed!=n&&is_prime(reversed);return ok(member,reversed,is_prime(n)?1:0);", S("13", True, True, 31, 1), (S("11", True, False, 11, 1), S("7", False, False, -1, -1))),
        Case("palindromic-prime-base", "Palindromic prime in a base", "long long n, long long base", "Require primality and equality with the complete base-b digit reversal.", "radix reversal plus independent primality", "2 <= n <= 1000000000 and 2 <= base <= 16", "compare extracted digit sequence from both ends", "testing decimal text in every base", ("prime", "reverse"), "if(n<2||n>1000000000||base<2||base>16)return bad();long long reversed=reverse_base(n,base),digits=1,x=n;while(x>=base){x/=base;++digits;}return ok(is_prime(n)&&reversed==n,digits,reversed);", S("17,2", True, True, 5, 17), (S("19,2", True, False, 5, 25), S("1,10", False, False, -1, -1))),
        Case("additive-persistence", "Additive persistence", "long long n, long long base", "Count digit-sum rounds to one digit and return the digital root.", "iterated radix digit-sum descent", "0 <= n <= 1000000000 and 2 <= base <= 16", "repeat digit extraction until below the base", "returning a digital-root formula as the round count", ("digit_sum",), "if(n<0||n>1000000000||base<2||base>16)return bad();long long rounds=0;while(n>=base){n=digit_sum(n,base);++rounds;}return ok(rounds>=2,rounds,n);", S("199,10", True, True, 3, 1), (S("18,10", True, False, 1, 9), S("1,1", False, False, -1, -1))),
        Case("multiplicative-persistence", "Multiplicative persistence", "long long n, long long base", "Count digit-product rounds to one digit with a bounded-state guard.", "iterated radix digit-product descent", "0 <= n <= 1000000000 and 2 <= base <= 16", "extract and multiply every digit at every round", "dropping zero digits from the product", (), "if(n<0||n>1000000000||base<2||base>16)return bad();long long rounds=0;while(n>=base){long long product=1,x=n;do{product*=x%base;x/=base;}while(x>0);n=product;++rounds;}return ok(rounds>=3,rounds,n);", S("77,10", True, True, 4, 8), (S("25,10", True, False, 2, 0), S("1,1", False, False, -1, -1))),
        Case("factorial-prime-valuation", "Factorial prime valuation", "long long n, long long prime", "Compute the exponent of a prime in n factorial using quotient layers.", "Legendre quotient-layer accumulation", "0 <= n <= 1000000000 and 2 <= prime <= 100000 with prime prime", "count multiples of every prime power", "counting multiples of p only once", ("prime",), "if(n<0||n>1000000000||prime<2||prime>100000||!is_prime(prime))return bad();long long value=0,x=n;while(x>0){x/=prime;value+=x;}return ok(value>0,value,prime);", S("10,2", True, True, 8, 2), (S("3,5", True, False, 0, 5), S("5,4", False, False, -1, -1))),
        Case("binomial-base-trailing-zeros", "Binomial base trailing zeros", "long long n, long long k, long long base", "Count trailing base-b zeros of C(n,k) by prime valuations.", "factor-base valuation bottleneck over factorial quotients with least-prime tie break", "0 <= k <= n <= 1000000 and 2 <= base <= 100000", "factor the base and compute each factorial valuation independently", "checking only factors two and five", ("factor",), "if(n<0||n>1000000||k<0||k>n||base<2||base>100000)return bad();auto fb=factors(base);long long answer=1000000000,bottleneck=-1;for(auto q:fb){long long p=q.first,v=0;for(long long x=n;x;x/=p)v+=x/p;for(long long x=k;x;x/=p)v-=x/p;for(long long x=n-k;x;x/=p)v-=x/p;long long z=v/q.second;if(z<answer){answer=z;bottleneck=p;}}return ok(answer>0,answer,bottleneck);", S("25,5,10", True, True, 1, 2), (S("10,2,10", True, False, 0, 2), S("5,6,10", False, False, -1, -1))),
        Case("linear-diophantine-class", "Linear Diophantine class", "long long a, long long b, long long c", "Classify ax+by=c and return the gcd and reduced right-hand side.", "Bezout gcd divisibility criterion with zero-pair handling", "abs(a),abs(b),abs(c) <= 1000000000 and a,b not both zero", "enumerate bounded residues then check the gcd theorem", "requiring both coefficients to divide c separately", ("gcd",), "if(a<-1000000000||a>1000000000||b<-1000000000||b>1000000000||c<-1000000000||c>1000000000||(a==0&&b==0))return bad();long long g=gcdll(a,b);return ok(c%g==0,g,c/g);", S("6,9,30", True, True, 3, 10), (S("6,9,20", True, False, 3, 6), S("0,0,0", False, False, -1, -1))),
        Case("primitive-pythagorean-triple", "Primitive Pythagorean triple", "long long a, long long b, long long c", "Classify a positive ordered triple as primitive Pythagorean and return perimeter and area.", "sorted-leg square identity plus three-way gcd", "1 <= a,b,c <= 1000000", "check the exact integer identity and pairwise gcd", "accepting scaled triples or assuming the largest argument is c", ("gcd",), "if(a<1||b<1||c<1||a>1000000||b>1000000||c>1000000)return bad();if(a>b){long long t=a;a=b;b=t;}bool equation=a*a+b*b==c*c;long long g=gcdll(gcdll(a,b),c);return ok(equation&&g==1,a+b+c,a*b/2);", S("3,4,5", True, True, 12, 6), (S("6,8,10", True, False, 24, 24), S("0,4,5", False, False, -1, -1))),
    )
    if len(rows) != 40 or len({row.task_id for row in rows}) != 40:
        raise AssertionError("the count-plan cell must contain exactly 40 unique roots")
    return rows


CASES = _cases()

# Cycle-01 remediation changes public examples only where the named coherent
# misconception must pass the public test before a private counterexample
# rejects it. These are owner inputs, not post-generation edits.
VISIBLE_OVERRIDES = {
    "factor-exponent-signature": S("30", True, True, 3, 5),
    "k-almost-prime-membership": S("30,3", True, True, 3, 5),
    "powerful-number-witness": S("36", True, True, 2, 3),
    "roughness-bound-profile": S("49,7", True, True, 7, 1),
    "radical-square-kernel": S("30", True, True, 30, 1),
    "liouville-parity": S("30", True, False, -1, 3),
    "totient-density-class": S("2", True, False, 1, 1),
    "carmichael-exponent-bound": S("5", True, False, 4, 1),
    "linear-congruence-solver": S("3,4,7", True, True, 6, 7),
    "quadratic-residue-witness": S("1,13", True, True, 1, 1),
    "lucas-index-membership": S("1", True, True, 1, 1),
    "polygonal-index-membership": S("21,3", True, True, 6, 21),
    "centered-polygonal-membership": S("1,5", True, True, 1, 1),
    "consecutive-sum-profile": S("9", True, True, 2, 2),
    "palindromic-prime-base": S("11,10", True, True, 2, 11),
    "additive-persistence": S("18,10", True, False, 1, 9),
    "factorial-prime-valuation": S("3,5", True, False, 0, 5),
    "linear-diophantine-class": S("6,9,18", True, True, 3, 6),
}

EXTRA_SAMPLES = {
    "prime-interval-profile": (S("2,5", True, True, 3, 5),),
    "k-almost-prime-membership": (S("72,1", True, False, 5, 3),),
    "squarefree-certificate": (S("18", True, False, 2, 3),),
    "powerful-number-witness": (S("72", True, True, 2, 3),),
    "multiplicative-order": (S("2,7", True, True, 3, 1),),
    "crt-pair-merge": (S("0,1,0,3", False, False, -1, -1),),
    "jacobi-symbol": (S("2,15", True, True, 1, 1),),
    "fibonacci-index-membership": (S("1", True, True, 1, 1),),
    "consecutive-sum-profile": (S("15", True, True, 3, 2),),
    "harshad-quotient": (S("10,2", True, True, 2, 5),),
    "smith-composite-class": (S("27", True, True, 9, 9),),
    "binomial-base-trailing-zeros": (S("6,3,6", True, False, 0, 3),),
    "liouville-parity": (S("4", True, True, 1, 2),),
}

UPPER_BOUND_SAMPLES = {
    "prime-interval-profile": (S("1000000,1000000", True, False, 0, -1), S("1000000,1000001", False, False, -1, -1)),
    "factor-exponent-signature": (S("1000000000", True, True, 18, 5), S("1000000001", False, False, -1, -1)),
    "semiprime-factor-pair": (S("1000000000", True, False, 18, 5), S("1000000001", False, False, -1, -1)),
    "k-almost-prime-membership": (S("1000000000,20", True, False, 18, 5), S("1000000001,20", False, False, -1, -1)),
    "squarefree-certificate": (S("1000000000", True, False, 2, 2), S("1000000001", False, False, -1, -1)),
    "powerful-number-witness": (S("1000000000", True, True, 2, 5), S("1000000001", False, False, -1, -1)),
    "smoothness-bound-profile": (S("1000000000,1000000000", True, True, 5, 2), S("1000000001,1000000000", False, False, -1, -1)),
    "roughness-bound-profile": (S("1000000000,1000000000", True, False, 2, 2), S("1000000001,1000000000", False, False, -1, -1)),
    "radical-square-kernel": (S("1000000000", True, False, 10, 100000000), S("1000000001", False, False, -1, -1)),
    "liouville-parity": (S("1000000000", True, True, 1, 18), S("1000000001", False, False, -1, -1)),
    "mobius-squarefree-sign": (S("1000000000", True, False, 0, 2), S("1000000001", False, False, -1, -1)),
    "totient-density-class": (S("1000000000", True, False, 400000000, 600000000), S("1000000001", False, False, -1, -1)),
    "carmichael-exponent-bound": (S("1000000", True, True, 50000, 20), S("1000001", False, False, -1, -1)),
    "multiplicative-order": (S("1,100000", True, True, 1, 1), S("1,100001", False, False, -1, -1)),
    "modular-inverse": (S("1000000000,1000000000", True, False, 0, 1000000000), S("1000000001,2", False, False, -1, -1)),
    "linear-congruence-solver": (S("1000000000,1000000000,1000000000", True, True, 0, 1), S("1000000001,0,2", False, False, -1, -1)),
    "crt-pair-merge": (S("1000000000,1000000,1000000000,1000000", True, True, 0, 1000000), S("0,1000001,0,2", False, False, -1, -1)),
    "quadratic-residue-witness": (S("1000000000,99991", True, True, 90000, 300), S("0,100001", False, False, -1, -1)),
    "jacobi-symbol": (S("0,1000000001", True, False, 0, 1000000001), S("0,1000000003", False, False, -1, -1)),
    "primitive-root-verifier": (S("99990,99991", True, False, 2, 99990), S("1,100001", False, False, -1, -1)),
    "fibonacci-index-membership": (S("1000000000", True, False, 45, 701408733), S("1000000001", False, False, -1, -1)),
    "lucas-index-membership": (S("1000000000", True, False, 44, 969323029), S("1000000001", False, False, -1, -1)),
    "triangular-index-membership": (S("1000000000", True, False, 44721, 1000006281), S("1000000001", False, False, -1, -1)),
    "polygonal-index-membership": (S("1000000000,12", True, False, 14143, 1000065673), S("1000000001,12", False, False, -1, -1)),
    "centered-polygonal-membership": (S("1000000000,12", True, False, 12911, 1000086061), S("1000000001,12", False, False, -1, -1)),
    "consecutive-sum-profile": (S("1000000000", True, True, 9, 5), S("1000000001", False, False, -1, -1)),
    "happy-cycle-class": (S("1000000000", True, True, 1, 1), S("1000000001", False, False, -1, -1)),
    "narcissistic-base-class": (S("1000000000,16", True, False, 887393859, 8), S("1000000001,16", False, False, -1, -1)),
    "kaprekar-split-witness": (S("1000000,16", True, False, 0, -1), S("1000001,16", False, False, -1, -1)),
    "automorphic-suffix-class": (S("1000000000,16", True, False, 4294967296, 2808348672), S("1000000001,16", False, False, -1, -1)),
    "harshad-quotient": (S("1000000000,16", True, False, 55, 10), S("1000000001,16", False, False, -1, -1)),
    "smith-composite-class": (S("1000000000", True, False, 1, 63), S("1000000001", False, False, -1, -1)),
    "emirp-reversal-class": (S("1000000000", True, False, 1, 0), S("1000000001", False, False, -1, -1)),
    "palindromic-prime-base": (S("1000000000,16", True, False, 8, 11315635), S("1000000001,16", False, False, -1, -1)),
    "additive-persistence": (S("1000000000,16", True, True, 2, 10), S("1000000001,16", False, False, -1, -1)),
    "multiplicative-persistence": (S("1000000000,16", True, False, 1, 0), S("1000000001,16", False, False, -1, -1)),
    "factorial-prime-valuation": (S("1000000000,99991", True, True, 10000, 99991), S("1000000001,99991", False, False, -1, -1)),
    "binomial-base-trailing-zeros": (S("1000000,0,100000", True, False, 0, 2), S("1000001,0,100000", False, False, -1, -1)),
    "linear-diophantine-class": (S("1000000000,1000000000,1000000000", True, True, 1000000000, 1), S("1000000001,1,1", False, False, -1, -1)),
    "primitive-pythagorean-triple": (S("1000000,1000000,1000000", True, False, 3000000, 500000000000), S("1000000,1000000,1000001", False, False, -1, -1)),
}

MEMBER_PREDICATES = {
    "prime-interval-profile": "the closed interval contains at least one prime",
    "factor-exponent-signature": "the exact total prime-factor multiplicity is greater than one",
    "radical-square-kernel": "the radical equals n (equivalently, n is square-free)",
    "liouville-parity": "the Liouville sign is +1",
    "mobius-squarefree-sign": "the Mobius value is nonzero",
    "carmichael-exponent-bound": "lambda(n) is strictly less than n-1",
    "jacobi-symbol": "the Jacobi symbol is exactly +1",
    "consecutive-sum-profile": "at least one positive consecutive-sum representation exists",
    "additive-persistence": "at least two digit-sum rounds are required",
    "multiplicative-persistence": "at least three digit-product rounds are required",
    "factorial-prime-valuation": "the factorial valuation is positive",
    "binomial-base-trailing-zeros": "the trailing-zero count is positive",
}

NEGATIVE_COUNTEREXAMPLES = {
    "prime-interval-profile": S("2,5", True, True, 3, 5),
    "factor-exponent-signature": S("72", True, True, 5, 3),
    "semiprime-factor-pair": S("12", True, False, 3, 3),
    "k-almost-prime-membership": S("72,1", True, False, 5, 3),
    "squarefree-certificate": S("18", True, False, 2, 3),
    "powerful-number-witness": S("72", True, True, 2, 3),
    "smoothness-bound-profile": S("70,5", True, False, 7, 3),
    "roughness-bound-profile": S("21,5", True, False, 3, 2),
    "radical-square-kernel": S("72", True, False, 6, 12),
    "liouville-parity": S("4", True, True, 1, 2),
    "mobius-squarefree-sign": S("12", True, False, 0, 2),
    "totient-density-class": S("9", True, True, 6, 3),
    "carmichael-exponent-bound": S("8", True, True, 2, 4),
    "multiplicative-order": S("2,7", True, True, 3, 1),
    "modular-inverse": S("6,9", True, False, 0, 3),
    "linear-congruence-solver": S("6,8,14", True, True, 6, 7),
    "crt-pair-merge": S("1,4,3,6", True, True, 9, 12),
    "quadratic-residue-witness": S("10,13", True, True, 10, 6),
    "jacobi-symbol": S("2,15", True, True, 1, 1),
    "primitive-root-verifier": S("4,5", True, False, 2, 4),
    "fibonacci-index-membership": S("1", True, True, 1, 1),
    "lucas-index-membership": S("47", True, True, 8, 47),
    "triangular-index-membership": S("22", True, False, 7, 28),
    "polygonal-index-membership": S("22,5", True, True, 4, 22),
    "centered-polygonal-membership": S("31,5", True, True, 4, 31),
    "consecutive-sum-profile": S("15", True, True, 3, 2),
    "happy-cycle-class": S("2", True, False, 9, 4),
    "narcissistic-base-class": S("10,2", True, False, 2, 4),
    "kaprekar-split-witness": S("10,10", True, False, 0, -1),
    "automorphic-suffix-class": S("26,10", True, False, 100, 76),
    "harshad-quotient": S("10,2", True, True, 2, 5),
    "smith-composite-class": S("27", True, True, 9, 9),
    "emirp-reversal-class": S("11", True, False, 11, 1),
    "palindromic-prime-base": S("17,2", True, True, 5, 17),
    "additive-persistence": S("199,10", True, True, 3, 1),
    "multiplicative-persistence": S("25,10", True, False, 2, 0),
    "factorial-prime-valuation": S("10,2", True, True, 8, 2),
    "binomial-base-trailing-zeros": S("6,3,6", True, False, 0, 3),
    "linear-diophantine-class": S("6,9,30", True, True, 3, 10),
    "primitive-pythagorean-triple": S("6,8,10", True, False, 24, 24),
}

# Exact prompt-visible meanings. The first sentence (Case.summary) defines
# member. These fields define outputs for both member and non-member branches.
OUTPUT_FIELDS = {
    "prime-interval-profile": ("the number of primes in the interval", "the greatest prime, or -1 when none exist"),
    "factor-exponent-signature": ("the total prime-factor multiplicity", "the greatest prime factor, or 1 for n=1"),
    "semiprime-factor-pair": ("the smaller factor for a semiprime, otherwise total multiplicity", "the larger factor, or greatest discovered prime for a non-member"),
    "k-almost-prime-membership": ("the exact total prime-factor multiplicity", "the greatest processed prime factor"),
    "squarefree-certificate": ("the number of distinct prime factors", "the first repeated prime on failure, otherwise the greatest prime factor or 1"),
    "powerful-number-witness": ("the number of distinct prime factors", "the first exponent-one prime on failure, otherwise the greatest prime factor or 1"),
    "smoothness-bound-profile": ("the largest prime factor", "the number of distinct prime factors"),
    "roughness-bound-profile": ("the smallest prime factor", "the number of distinct prime factors"),
    "radical-square-kernel": ("the radical, the product of distinct prime factors", "n divided by the radical"),
    "liouville-parity": ("the Liouville sign, +1 or -1", "the total prime-factor multiplicity"),
    "mobius-squarefree-sign": ("the Mobius value (-1, 0, or +1)", "the first repeated prime when zero, otherwise the distinct-factor count"),
    "totient-density-class": ("Euler's totient phi(n)", "n minus phi(n)"),
    "carmichael-exponent-bound": ("the Carmichael lambda value", "n divided by lambda(n)"),
    "multiplicative-order": ("the least positive order, or 0 when non-coprime", "1 for a found order, otherwise gcd(a, modulus)"),
    "modular-inverse": ("the least nonnegative inverse, or 0 when absent", "1 when invertible, otherwise the positive gcd"),
    "linear-congruence-solver": ("the least nonnegative solution, or 0 when unsolvable", "the reduced modulus when solvable, otherwise gcd(a,m)"),
    "crt-pair-merge": ("the least merged residue, or 0 when incompatible", "the lcm modulus when compatible, otherwise the modulus gcd"),
    "quadratic-residue-witness": ("the normalized residue", "the least square root, or -1 when no root exists"),
    "jacobi-symbol": ("the Jacobi symbol (-1, 0, or +1)", "the final gcd state; 1 exactly when the symbol is nonzero"),
    "primitive-root-verifier": ("the exact multiplicative order", "prime minus one"),
    "fibonacci-index-membership": ("the first index reached or the overshoot index", "n when present, otherwise the greatest preceding Fibonacci value"),
    "lucas-index-membership": ("the first index reached or the overshoot index", "n when present, otherwise the greatest preceding Lucas value"),
    "triangular-index-membership": ("the matching or first overshoot index", "the triangular value at that index"),
    "polygonal-index-membership": ("the matching or first overshoot index", "the polygonal value at that index"),
    "centered-polygonal-membership": ("the matching or first overshoot layer", "the centered polygonal value at that layer"),
    "consecutive-sum-profile": ("the number of positive consecutive-sum representations", "the shortest length, or -1 when absent"),
    "happy-cycle-class": ("steps to one or to the first repeated state", "1 for a happy orbit, otherwise the first repeated state"),
    "narcissistic-base-class": ("the computed digit-power sum", "the base-b digit count"),
    "kaprekar-split-witness": ("the least right-part digit count, or 0 when absent", "the right part, or -1 when absent"),
    "automorphic-suffix-class": ("base raised to the digit width", "the square suffix of that width"),
    "harshad-quotient": ("the base-b digit sum", "the quotient when divisible, otherwise the remainder"),
    "smith-composite-class": ("the decimal digit sum of n", "the prime-factor digit sum, or n itself for a prime"),
    "emirp-reversal-class": ("the decimal reversal", "1 when n is prime, otherwise 0"),
    "palindromic-prime-base": ("the base-b digit count", "the complete base-b reversal"),
    "additive-persistence": ("the number of digit-sum rounds", "the final one-digit value"),
    "multiplicative-persistence": ("the number of digit-product rounds", "the final one-digit value"),
    "factorial-prime-valuation": ("the exponent of prime in n factorial", "the validated prime"),
    "binomial-base-trailing-zeros": ("the trailing-zero count", "the least prime factor attaining the minimum valuation ratio"),
    "linear-diophantine-class": ("gcd(abs(a),abs(b))", "c divided by that gcd, truncated only after divisibility classification"),
    "primitive-pythagorean-triple": ("the perimeter", "the integer area a*b/2 after ordering the legs"),
}


def _visible(case: Case) -> Sample:
    return VISIBLE_OVERRIDES.get(case.task_id, case.visible)


def _private_samples(case: Case) -> tuple[Sample, ...]:
    samples = [_visible(case)]
    if case.visible not in samples:
        samples.append(case.visible)
    samples.extend(case.private)
    samples.extend(EXTRA_SAMPLES.get(case.task_id, ()))
    samples.extend(UPPER_BOUND_SAMPLES[case.task_id])
    unique: list[Sample] = []
    for sample in samples:
        if sample not in unique:
            unique.append(sample)
    return tuple(unique)


NEGATIVE_MUTATIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "prime-interval-profile": (("if(is_prime(n))", "if(n!=2&&is_prime(n))"),),
    "factor-exponent-signature": (("omega+=q.second", "omega+=(q.second>0?1:0)"),),
    "semiprime-factor-pair": (("if(total!=2)", "if(f.size()>2)"),),
    "k-almost-prime-membership": (("total+=q.second", "total+=(q.second>0?1:0)"),),
    "squarefree-certificate": (("if(q.second>1)", "if(q.first==2&&q.second>1)"),),
    "powerful-number-witness": (("for(auto q:f)if(q.second<2)return ok(false,(long long)f.size(),q.first);", "long long root=1;while(root<=n/root&&root*root<n)++root;if(root*root!=n)return ok(false,(long long)f.size(),f.front().first);"),),
    "smoothness-bound-profile": (("long long largest=f.back().first;", "long long largest=1;for(auto q:f)if(q.first<=bound)largest=q.first;"),),
    "roughness-bound-profile": (("long long smallest=f.front().first;", "long long smallest=f.back().first;"),),
    "radical-square-kernel": (("for(auto q:f)rad*=q.first;", "for(auto q:f)for(long long i=0;i<q.second;++i)rad*=q.first;"),),
    "liouville-parity": (("omega+=q.second", "omega+=(q.second>0?1:0)"),),
    "mobius-squarefree-sign": (("if(q.second>1)return ok(false,0,q.first);", "if(q.second>1){long long omega=0;for(auto r:f)omega+=r.second;return ok(true,(omega%2==0)?1:-1,q.first);}"),),
    "totient-density-class": (("phi=phi/q.first*(q.first-1)", "phi-=(q.first>0?1:0)"),),
    "carmichael-exponent-bound": (("if(p==2&&e>=3)term/=2;", "if(false&&p==2&&e>=3)term/=2;"),),
    "multiplicative-order": (("return ok(true,k,cur)", "return ok(true,modulus-1,cur)"),),
    "modular-inverse": (("if(g!=1&&g!=-1)return ok(false,0,g<0?-g:g);", "if(false&&g!=1&&g!=-1)return ok(false,0,g<0?-g:g);"),),
    "linear-congruence-solver": (("if(b%g!=0)return ok(false,0,g);", "if(g!=1||b%g!=0)return ok(false,0,g);"),),
    "crt-pair-merge": (("long long mod=m1/g*m2;", "long long mod=m1*m2;"),),
    "quadratic-residue-witness": (("return ok(true,residue,x)", "return ok(true,residue,residue)"),),
    "jacobi-symbol": (("long long n=odd_modulus;", "long long original=a%odd_modulus;if(original<0)original+=odd_modulus;long long n=odd_modulus;"), ("return ok(n==1&&result==1,n==1?result:0,n);", "bool has_root=false;for(long long x=0;x<odd_modulus;++x)if((x*x)%odd_modulus==original)has_root=true;return ok(n==1&&result==1&&has_root,n==1?result:0,n);")),
    "primitive-root-verifier": (("return ok(order==prime-1,order,prime-1);", "return ok(generator!=0,order,prime-1);"),),
    "fibonacci-index-membership": (("if(n==0)return ok(true,0,0);", "if(n==0)return ok(true,0,0);if(n==1)return ok(true,2,1);"),),
    "lucas-index-membership": (("long long a=2,b=1,index=1;", "long long a=0,b=1,index=1;"),),
    "triangular-index-membership": (("long long value=0,k=0;while(value<n){++k;value+=k;}", "long long k=0;while((k+1)*(k+1)<=2*n)++k;long long value=k*(k+1)/2;"),),
    "polygonal-index-membership": (("delta=sides-1", "delta=2"), ("delta+=sides-2", "delta+=1")),
    "centered-polygonal-membership": (("long long value=1,k=1;while(value<n){value+=sides*k;++k;}", "long long value=1,k=1,delta=sides-1;while(value<n){++k;value+=delta;delta+=sides-2;}"),),
    "consecutive-sum-profile": (("len*(len+1)/2<=n", "len*(len-1)/2<=n"), ("rem>0", "rem>=0")),
    "happy-cycle-class": (("while(n!=1){", "while(n!=1&&steps<8){"), ("return ok(true,steps,1);", "if(n!=1)return ok(false,steps,n);return ok(true,steps,1);")),
    "narcissistic-base-class": (("digit_power_sum(n,base,count)", "digit_power_sum(n,10,3)"),),
    "kaprekar-split-witness": (("right>0", "right>=0"),),
    "automorphic-suffix-class": (("square%modulus==n", "square%base==n%base"),),
    "harshad-quotient": (("digit_sum(n,base)", "digit_sum(n,10)"),),
    "smith-composite-class": (("for(auto q:f)for(long long i=0;i<q.second;++i)sum+=digit_sum(q.first,10);", "for(auto q:f)sum+=digit_sum(q.first,10);"),),
    "emirp-reversal-class": (("&&reversed!=n", ""),),
    "palindromic-prime-base": (("reverse_base(n,base)", "reverse_base(n,10)"),),
    "additive-persistence": (("while(n>=base){n=digit_sum(n,base);++rounds;}", "if(n>=base){n=digit_sum(n,base);rounds=1;while(n>=base)n=digit_sum(n,base);}"),),
    "multiplicative-persistence": (("product*=x%base", "if(x%base!=0)product*=x%base"),),
    "factorial-prime-valuation": (("long long value=0,x=n;while(x>0){x/=prime;value+=x;}", "long long value=n/prime,x=0;(void)x;"),),
    "binomial-base-trailing-zeros": (("auto fb=factors(base);", "auto all=factors(base);std::vector<std::pair<long long,long long>> fb{all.front()};"),),
    "linear-diophantine-class": (("return ok(c%g==0,g,c/g);", "return ok(c%a==0&&c%b==0,g,c/g);"),),
    "primitive-pythagorean-triple": (("equation&&g==1", "equation&&(g>0)"),),
}


def _negative_body(case: Case) -> str:
    body = case.body
    for old, new in NEGATIVE_MUTATIONS[case.task_id]:
        if old not in body:
            _fail("negative_mutation_missing", f"{case.task_id}:{old}")
        body = body.replace(old, new, 1)
    if body == case.body:
        _fail("negative_mutation_missing", case.task_id)
    return body


def _fail(code: str, detail: str = "") -> None:
    raise CreatorError(f"{code}:{detail}" if detail else code)


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    return _sha(path.read_bytes())


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _write_json(path: Path, value: object) -> None:
    _write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".state" not in p.parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _safe_out(out: Path) -> Path:
    resolved = out.resolve(strict=False)
    if resolved != DEFAULT_OUT.resolve(strict=False):
        _fail("invalid_output_root", str(out))
    if out.is_symlink() or any(parent.is_symlink() for parent in (out.parent, out.parent.parent)):
        _fail("invalid_output_root", "symlink")
    for old in EXISTING_ROOTS:
        old_resolved = old.resolve(strict=False)
        if resolved == old_resolved or old_resolved in resolved.parents:
            _fail("invalid_output_root", str(old))
    return resolved


def _existing_ids(exclude: Path | None = None) -> dict[str, str]:
    excluded = exclude.resolve(strict=False) if exclude else None
    found: dict[str, str] = {}
    for base in (*EXISTING_ROOTS, EXPANSION_ROOT):
        if not base.is_dir():
            continue
        for config in base.rglob(".meta/config.json"):
            resolved = config.resolve(strict=False)
            if ".state" in config.parts or (excluded and excluded in resolved.parents):
                continue
            found.setdefault(config.parent.parent.name, str(config.parent.parent.relative_to(REPO_ROOT)))
    return found


def _support(features: tuple[str, ...]) -> str:
    result = ""
    if "gcd" in features:
        result += "long long gcdll(long long a,long long b){if(a<0)a=-a;if(b<0)b=-b;while(b){long long r=a%b;a=b;b=r;}return a;}\n"
    if "egcd" in features:
        result += "long long egcd(long long a,long long b,long long& x,long long& y){if(b==0){x=a<0?-1:1;y=0;return a<0?-a:a;}long long x1=0,y1=0;long long g=egcd(b,a%b,x1,y1);x=y1;y=x1-(a/b)*y1;return g;}\n"
    if "factor" in features:
        result += "std::vector<std::pair<long long,long long>> factors(long long n){std::vector<std::pair<long long,long long>> out;for(long long p=2;p<=n/p;++p){if(n%p)continue;long long e=0;do{n/=p;++e;}while(n%p==0);out.push_back({p,e});}if(n>1)out.push_back({n,1});return out;}\n"
    if "prime" in features:
        result += "bool is_prime(long long n){if(n<2)return false;if(n%2==0)return n==2;for(long long d=3;d<=n/d;d+=2)if(n%d==0)return false;return true;}\n"
    if "digit_sum" in features:
        result += "long long digit_sum(long long n,long long base){long long sum=0;do{sum+=n%base;n/=base;}while(n);return sum;}\n"
    if "reverse" in features:
        result += "long long reverse_base(long long n,long long base){long long value=0;do{value=value*base+n%base;n/=base;}while(n);return value;}\n"
    if "digit_power" in features:
        result += "long long digit_power_sum(long long n,long long base,long long power){long long sum=0;do{long long digit=n%base,term=1;for(long long i=0;i<power;++i)term*=digit;sum+=term;n/=base;}while(n);return sum;}\n"
    if "gcd" in features and "factor" in features:
        result += "long long lcmll(long long a,long long b){return a/gcdll(a,b)*b;}\n"
    return result


def _header(case: Case) -> str:
    guard = case.snake.upper() + "_H"
    return f"""#ifndef {guard}\n#define {guard}\n#include <cstdint>\nnamespace {case.namespace} {{\nstruct Result {{ bool valid; bool member; std::int64_t value; std::int64_t witness; }};\nResult {case.function}({case.params});\n}}\n#endif\n"""


def _source(case: Case) -> str:
    includes = "#include <utility>\n#include <vector>\n" if "factor" in case.features or case.task_id == "happy-cycle-class" else ""
    helpers = _support(case.features)
    return f"""#include \"{case.task_id}.h\"\n{includes}namespace {case.namespace} {{\nnamespace {{\n+Result bad(){{return {{false,false,-1,-1}};}}\n+Result ok(bool member,long long value,long long witness){{return {{true,member,value,witness}};}}\n+{helpers}}}\n+Result {case.function}({case.params}){{{case.body}}}\n+}}\n""".replace("\n+", "\n")


def _starter(case: Case) -> str:
    voids = "".join(f"(void){name};" for name in case.param_names)
    return f"""#include \"{case.task_id}.h\"\nnamespace {case.namespace} {{\nResult {case.function}({case.params}) {{{voids}return {{false,false,-1,-1}};}}\n}}\n"""


def _assertion(case: Case, sample: Sample, number: int) -> str:
    v = "true" if sample.valid else "false"
    m = "true" if sample.member else "false"
    return f"{{auto r={case.function}({sample.args});if(r.valid!={v}||r.member!={m}||r.value!={sample.value}LL||r.witness!={sample.witness}LL)return {number};}}"


def _test(case: Case, *, private: bool, samples: tuple[Sample, ...] | None = None) -> str:
    samples = samples if samples is not None else (_private_samples(case) if private else (_visible(case),))
    assertions = "".join(_assertion(case, sample, index + 1) for index, sample in enumerate(samples))
    return f"""#include \"{case.task_id}.h\"\nusing {case.namespace}::{case.function};\nint main(){{{assertions}return 0;}}\n"""


def _negative(case: Case) -> str:
    includes = "#include <utility>\n#include <vector>\n" if "factor" in case.features or case.task_id in {"happy-cycle-class", "binomial-base-trailing-zeros"} else ""
    return f"""#include \"{case.task_id}.h\"\n{includes}namespace {case.namespace} {{\nnamespace {{\n+Result bad(){{return {{false,false,-1,-1}};}}\n+Result ok(bool member,long long value,long long witness){{return {{true,member,value,witness}};}}\n+{_support(case.features)}}}\n+Result {case.function}({case.params}){{{_negative_body(case)}}}\n+}}\n""".replace("\n+", "\n")


def _cmake(case: Case) -> str:
    return f"""cmake_minimum_required(VERSION 3.16)\nproject({case.snake} LANGUAGES CXX)\nset(CMAKE_CXX_STANDARD 17)\nset(CMAKE_CXX_STANDARD_REQUIRED ON)\nset(CMAKE_CXX_EXTENSIONS OFF)\nadd_compile_options(-Wall -Wextra -Wpedantic -Werror)\nenable_testing()\nadd_executable(visible {case.task_id}.cpp visible_test.cpp)\nadd_executable(private {case.task_id}.cpp .meta/private_test.cpp)\nadd_executable(negative_smoke .meta/negative.cpp visible_test.cpp)\nadd_executable(negative_rejected .meta/negative.cpp .meta/negative_test.cpp)\ntarget_include_directories(visible PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})\ntarget_include_directories(private PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})\ntarget_include_directories(negative_smoke PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})\ntarget_include_directories(negative_rejected PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})\nadd_test(NAME visible COMMAND visible)\nadd_test(NAME private COMMAND private)\nadd_test(NAME negative_smoke COMMAND negative_smoke)\nadd_test(NAME negative_rejected COMMAND negative_rejected)\nset_tests_properties(negative_rejected PROPERTIES WILL_FAIL TRUE)\n"""


def _semantic(case: Case) -> dict[str, list[str]]:
    return {
        "public_api": [case.params, "valid/member/value/witness", case.summary],
        "owned_state_or_algorithm": [case.algorithm, *case.features],
        "mutation_or_selection_rules": [case.summary, f"result-semantics:{case.task_id}"],
        "invalid_and_boundary_behavior": [case.boundary, f"false-member:{case.private[0].args}:{case.private[0].value}:{case.private[0].witness}", "invalid-sentinel:-1/-1"],
        "reference_control_flow": [case.algorithm, _sha(case.body.encode())],
        "deterministic_oracle": [case.oracle, *(sample.args for sample in _private_samples(case))],
        "topic_specific_negative_fixture": [case.bad, _negative_body(case)],
    }


def _render(case: Case, root: Path) -> None:
    root.mkdir(parents=True)
    _write(root / ".docs/introduction.md", f"# {case.title}\n\nNumber theory hides inside everyday integer questions: Is this number prime? How many divisors does it have? What digit does it end on in another base? Each question has a definition that fits in one line and an edge case at every bound — zero, one, and the largest representable value.\n\nThis exercise is about one such classification, computed exactly within the stated bounds.\n")
    visible = _visible(case)
    value_meaning, witness_meaning = OUTPUT_FIELDS[case.task_id]
    member_predicate = MEMBER_PREDICATES.get(case.task_id, f"the classification stated here holds: {case.summary}")
    _write(root / ".docs/instructions.md", f"""# Instructions

Implement `{case.function}({case.params})` in namespace `{case.namespace}`. {case.summary}

The result is total and deterministic. `valid` is true exactly when `{case.boundary}`; invalid input returns `{{false,false,-1,-1}}`. For valid input, `member` is true exactly when {member_predicate}. `value` is {value_meaning}. `witness` is {witness_meaning}. Least, first, and greatest always refer to increasing integer order; an equal-valued tie selects the least prime, index, split width, or residue. Bounds are inclusive unless explicitly called half-open. A valid non-member still returns the defined diagnostic `value` and `witness`, never the invalid sentinel.

Public boundary example: `{visible.args}` returns `{{true,{str(visible.member).lower()},{visible.value},{visible.witness}}}`.

Compute the result by {case.algorithm}: {case.oracle}. In particular, {case.bad} does not satisfy this contract. Do not hard-code examples, use floating-point rounding, invoke external programs, or use third-party number-theory libraries. All arithmetic must remain within signed 64-bit range under the stated bounds.
""")
    _write(root / f"{case.task_id}.h", _header(case))
    _write(root / f"{case.task_id}.cpp", _starter(case))
    _write(root / "visible_test.cpp", _test(case, private=False))
    _write(root / "CMakeLists.txt", _cmake(case))
    _write(root / ".meta/example.h", _header(case))
    _write(root / ".meta/example.cpp", _source(case))
    _write(root / ".meta/private_test.cpp", _test(case, private=True))
    _write(root / ".meta/negative_test.cpp", _test(case, private=True, samples=(NEGATIVE_COUNTEREXAMPLES[case.task_id],)))
    _write(root / ".meta/negative.cpp", _negative(case))
    _write(root / ".meta/tests.toml", f'[visible]\ndescription="public boundary example"\n[private]\ndescription="member, non-member, invalid, boundary/tie: {case.oracle}; rejects {case.bad}"\n')
    assertions = []
    for index, sample in enumerate(_private_samples(case), start=1):
        requirements = ["valid_member" if sample.valid and sample.member else "valid_nonmember" if sample.valid else "invalid_input"]
        if sample == visible:
            requirements.append("public_example")
        if sample == UPPER_BOUND_SAMPLES[case.task_id][0]:
            requirements.extend(("published_upper_bound", "ordering_and_tie"))
        if sample == UPPER_BOUND_SAMPLES[case.task_id][1]:
            requirements.append("above_published_upper_bound")
        if sample == NEGATIVE_COUNTEREXAMPLES[case.task_id]:
            requirements.append("named_negative_counterexample")
        assertions.append({"assertion_id": f"private-{index}", "args": sample.args, "expected": {"valid": sample.valid, "member": sample.member, "value": sample.value, "witness": sample.witness}, "requirements": requirements})
    _write_json(root / ".meta/coverage.json", {"schema_version": "integer-requirement-coverage-v3", "task_id": case.task_id, "requirements": {"member_predicate": member_predicate, "named_negative": case.bad, "named_negative_body_hash": _sha(_negative_body(case).encode()), "named_negative_assertion": next(row["assertion_id"] for row in assertions if "named_negative_counterexample" in row["requirements"]), "published_upper_bound_assertion": next(row["assertion_id"] for row in assertions if "published_upper_bound" in row["requirements"]), "above_upper_bound_assertion": next(row["assertion_id"] for row in assertions if "above_published_upper_bound" in row["requirements"]), "ordering_and_tie_rule": witness_meaning}, "assertions": assertions, "status": "covered"})
    _write_json(root / ".meta/config.json", {
        "authors": ["w8-biayn"],
        "blurb": case.summary,
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": ["visible_test.cpp", ".meta/private_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    })
    semantic = _semantic(case)
    _write_json(root / ".meta/provenance.json", {
        "schema_version": "integer-number-theory-provenance-v3",
        "task_spec_revision": 3,
        "task_id": case.task_id,
        "family_id": FAMILY_ID,
        "lineage": "new-root",
        "source": str(CURRICULUM.relative_to(REPO_ROOT)),
        "owner": OWNER,
        "authoring": "clean-room repository-authored",
        "license": "CC0-1.0",
        "count_plan_cell": "numerical anchors: integer classification and bounded number-theory routines",
        "primary_core_objective": "achieved",
        "remedy_spec": str(REMEDY_SPEC.relative_to(REPO_ROOT)),
        "closed_finding_candidates": ["ICNT-AUD-001", "ICNT-AUD-002", "ICNT-AUD-003", "ICNT-AUD-004", "ICNT-AUD-005", "ICNT-AUD-006", "ICNT-AUD-007", "ICNT-AUD-008"],
        "diversity_signatures": semantic,
        "non_claim": "local task candidate only; no SFT release, training authorization, or benchmark claim",
    })


def _control_root(out: Path, name: str) -> Path:
    return out / ".state/adversarial-clone-controls" / name


def _write_controls(out: Path) -> None:
    base = out / CASES[0].task_id
    records = {}
    for name in ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection"):
        root = _control_root(out, name)
        shutil.copytree(base, root)
        changed: list[str] = []
        if name == "domain-identifier-renamed":
            for relative in (".docs/introduction.md", ".docs/instructions.md"):
                path = root / relative
                path.write_text(path.read_text().replace("Prime interval", "Beacon interval").replace("prime", "marked"))
                changed.append(relative)
        elif name == "constants-policy-only":
            for relative in (".docs/instructions.md", ".meta/example.cpp", ".meta/negative.cpp"):
                path = root / relative
                path.write_text(path.read_text().replace("1000000", "999999"))
                changed.append(relative)
            private = root / ".meta/private_test.cpp"
            private.write_text(private.read_text().replace("1000000,1000000", "999999,999999"))
            changed.append(".meta/private_test.cpp")
            coverage_path = root / ".meta/coverage.json"
            coverage = json.loads(coverage_path.read_text())
            for assertion in coverage["assertions"]:
                if assertion["args"] == "1000000,1000000":
                    assertion["args"] = "999999,999999"
                elif assertion["args"] == "1000000,1000001":
                    assertion["args"] = "999999,1000000"
            _write_json(coverage_path, coverage)
            changed.append(".meta/coverage.json")
        else:
            source = root / ".meta/example.cpp"
            source.write_text(source.read_text().replace("n<=hi", "n<hi"))
            changed.append(".meta/example.cpp")
            for relative in ("visible_test.cpp", ".meta/private_test.cpp", ".meta/negative_test.cpp"):
                path = root / relative
                path.write_text(path.read_text().replace("r.value!=4LL||r.witness!=19LL", "r.value!=3LL||r.witness!=17LL").replace("r.value!=3LL||r.witness!=5LL", "r.value!=2LL||r.witness!=3LL"))
                changed.append(relative)
            negative = root / ".meta/negative.cpp"
            negative.write_text(negative.read_text().replace("n<=hi", "n<hi"))
            changed.append(".meta/negative.cpp")
            instructions = root / ".docs/instructions.md"
            instructions.write_text(instructions.read_text().replace("closed interval", "half-open interval"))
            changed.append(".docs/instructions.md")
            coverage_path = root / ".meta/coverage.json"
            coverage = json.loads(coverage_path.read_text())
            coverage["requirements"]["member_predicate"] = coverage["requirements"]["member_predicate"].replace("closed interval", "half-open interval")
            for assertion in coverage["assertions"]:
                if assertion["args"] == "10,19":
                    assertion["expected"].update({"value": 3, "witness": 17})
                elif assertion["args"] == "2,5":
                    assertion["expected"].update({"value": 2, "witness": 3})
            _write_json(coverage_path, coverage)
            changed.append(".meta/coverage.json")
        records[name] = {"changed_files": sorted(changed), "source_task": CASES[0].task_id}
    _write_json(out / ".state/adversarial-clone-controls/manifest.json", {"schema_version": "integer-clone-controls-v1", "controls": records})


def materialize(out: Path = DEFAULT_OUT, *, force: bool = False) -> dict[str, object]:
    out = _safe_out(out)
    before_hashes: dict[str, str] = {}
    archived_state: dict[str, bytes] = {}
    preserved_history: dict[str, bytes] = {}
    archive_label = "pre-remediation-cycle-02"
    prior_cycles = ""
    collisions = sorted({case.task_id for case in CASES} & set(_existing_ids(exclude=out)))
    if collisions:
        _fail("existing_task_id", ",".join(collisions))
    if out.exists():
        manifest_path = out / ".state/manifest.json"
        if not force:
            _fail("output_exists", str(out))
        if not manifest_path.is_file() or json.loads(manifest_path.read_text()).get("owner") != OWNER:
            _fail("foreign_output_root", str(out))
        for case in CASES:
            prior_root = out / case.task_id
            if prior_root.is_dir():
                before_hashes[case.task_id] = _tree_hash(prior_root)
            prior_remedy = out / ".state/remedy" / f"{case.task_id}.json"
            if prior_remedy.is_file():
                record = json.loads(prior_remedy.read_text())
                if record.get("schema_version") == "aider-task-remedy-v2" and record.get("invalidated_audit_subject") == "sha256:5dec634b096d9133a0ea4744433edaf3043fc487ae1faa6d1263082fc0bf2ef7":
                    before_hashes[case.task_id] = record["tree_hash_before"]
        state_root = out / ".state"
        history_root = state_root / "history"
        if history_root.is_dir():
            preserved_history = {str(path.relative_to(history_root)): path.read_bytes() for path in history_root.rglob("*") if path.is_file()}
            labels = {Path(path).parts[0] for path in preserved_history}
            if archive_label in labels:
                archive_label = f"cycle-02-regeneration-attempt-{1 + sum(label.startswith('cycle-02-regeneration-attempt-') for label in labels):02d}"
        for prior in state_root.rglob("*"):
            if prior.is_file() and history_root not in prior.parents and prior.name != "cycles.jsonl":
                archived_state[str(prior.relative_to(state_root))] = prior.read_bytes()
        cycles = out / ".state/cycles.jsonl"
        if cycles.is_file():
            prior_cycles = cycles.read_text()
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for case in CASES:
        _render(case, out / case.task_id)
    _write_controls(out)
    history_root = out / ".state/history"
    for name, data in preserved_history.items():
        path = history_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    history = history_root / archive_label
    for name, data in archived_state.items():
        path = history / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    if prior_cycles:
        _write(out / ".state/cycles.jsonl", prior_cycles)
    generator_revision = _file_hash(REPO_ROOT / OWNER)
    affected_member = set(MEMBER_PREDICATES)
    for case in CASES:
        findings = ["ICNT-AUD-003", "ICNT-AUD-005", "ICNT-AUD-007", "ICNT-AUD-008"]
        if case.task_id in affected_member:
            findings.append("ICNT-AUD-001")
        if case.task_id == "k-almost-prime-membership":
            findings.append("ICNT-AUD-006")
        findings.append("ICNT-AUD-010")
        _write_json(out / ".state/remedy" / f"{case.task_id}.json", {
            "schema_version": "aider-task-remedy-v2",
            "task_id": case.task_id,
            "family_id_before": FAMILY_ID,
            "tree_hash_before": before_hashes.get(case.task_id, "sha256:unknown-new-root"),
            "tree_hash_after": _tree_hash(out / case.task_id),
            "generator_path": OWNER,
            "generator_revision": generator_revision,
            "invalidated_audit_subject": "sha256:88c86864d4034f55cb08d08cf1088fb8b3465d3cf6432d9f80d1629ce517211e",
            "finding_ids": findings,
            "disposition": "repair-in-place",
            "verification_receipt": f".state/remedy-verification/{case.task_id}.json",
            "license_screen": "pass",
            "remedy_spec_path": str(REMEDY_SPEC.relative_to(REPO_ROOT)),
            "remedy_spec_hash": _file_hash(REMEDY_SPEC),
            "status": "implemented_pending_verification",
        })
    manifest = {
        "schema_version": "integer-number-theory-family-v3",
        "family_id": FAMILY_ID,
        "owner": OWNER,
        "curriculum": str(CURRICULUM.relative_to(REPO_ROOT)),
        "curriculum_hash": _file_hash(CURRICULUM),
        "task_count": 40,
        "task_ids": [case.task_id for case in CASES],
        "status": "generated_pending_creator_preflight",
        "invalidated_audit_subject": "sha256:5dec634b096d9133a0ea4744433edaf3043fc487ae1faa6d1263082fc0bf2ef7",
        "remediation_findings": ["ICNT-AUD-001", "ICNT-AUD-003", "ICNT-AUD-005", "ICNT-AUD-006", "ICNT-AUD-007", "ICNT-AUD-008"],
        "selected_prompts": [
            "docs/aider-tasks-spec/prompts/generate-family-spec.md",
            "docs/aider-tasks-spec/prompts/implement-family-for-sft.md",
        ],
    }
    _write_json(out / ".state/manifest.json", manifest)
    manifest["tree_hash"] = _tree_hash(out)
    _write_json(out / ".state/manifest.json", manifest)
    return manifest


def _role_check(out: Path, case: Case) -> dict[str, object]:
    root = out / case.task_id
    config = json.loads((root / ".meta/config.json").read_text())
    expected = [f"{case.task_id}.h", f"{case.task_id}.cpp"]
    if config["files"]["solution"] != expected or config["files"]["example"] != [".meta/example.h", ".meta/example.cpp"]:
        _fail("role_conflict", case.task_id)
    prompt_files = [".docs/introduction.md", ".docs/instructions.md", *expected]
    for path in sum(config["files"].values(), []):
        relative = Path(path)
        if relative.is_absolute() or ".." in relative.parts or not (root / relative).is_file():
            _fail("unsafe_path", f"{case.task_id}:{path}")
    prompt = "\n".join((root / path).read_text() for path in prompt_files)
    for forbidden in (".meta/", "private_test", "example.cpp", "CMakeLists", "provenance", "receipt"):
        if forbidden in prompt:
            _fail("prompt_contract_incomplete", f"{case.task_id}:{forbidden}")
    for required in ("`valid`", "`member`", "`value`", "`witness`", *OUTPUT_FIELDS[case.task_id]):
        if required not in prompt:
            _fail("prompt_contract_incomplete", f"{case.task_id}:{required}")
    return {"task_id": case.task_id, "prompt_files": prompt_files, "status": "pass"}


def _artifact_tokens(text: str, case: Case) -> set[str]:
    for value in (case.task_id, case.snake, case.namespace, case.function, case.title.lower().replace(" ", "_")):
        text = text.replace(value, " task_symbol ")
        text = text.replace(value.replace("_", "-"), " task_symbol ")
    text = text.lower()
    raw = re.findall(r"[a-z_]+|\d+|<=|>=|==|!=|&&|\|\||[<>%*/+-]", text)
    return {f"{a}|{b}" for a, b in zip(raw, raw[1:])} | set(raw)


def _case_semantic(root: Path, case: Case, *, validate: bool = True) -> dict[str, list[str]]:
    docs = (root / ".docs/instructions.md").read_text()
    header = (root / f"{case.task_id}.h").read_text()
    source = (root / ".meta/example.cpp").read_text()
    private = (root / ".meta/private_test.cpp").read_text()
    negative = (root / ".meta/negative.cpp").read_text()
    coverage = (root / ".meta/coverage.json").read_text()
    required = (case.summary, case.algorithm, case.boundary, case.oracle, case.bad, *OUTPUT_FIELDS[case.task_id])
    if validate and (not all(value in docs for value in required) or case.body not in source or _negative_body(case) not in negative or not all(sample.args in private for sample in _private_samples(case))):
        _fail("invariant_not_enforced", case.task_id)
    surfaces = {
        "public_api": header + docs,
        "owned_state_or_algorithm": source + docs,
        "mutation_or_selection_rules": source + docs + coverage,
        "invalid_and_boundary_behavior": docs + private + coverage,
        "reference_control_flow": source,
        "deterministic_oracle": private + coverage,
        "topic_specific_negative_fixture": negative + coverage + docs,
    }
    return {dimension: sorted(_artifact_tokens(text, case)) for dimension, text in surfaces.items()}


def _pair_decision(left: dict[str, list[str]], right: dict[str, list[str]], *, threshold: float = 1.0) -> dict[str, dict[str, object]]:
    decisions = {}
    for dimension in DIMENSIONS:
        a, b = set(left[dimension]), set(right[dimension])
        shared = len(a & b) / max(1, len(a | b))
        decisions[dimension] = {"pass": a != b and shared < threshold, "jaccard": shared, "threshold": threshold}
    return decisions


def _aggregate_similarity(left: dict[str, list[str]], right: dict[str, list[str]]) -> float:
    a = {f"{dimension}:{token}" for dimension in DIMENSIONS for token in left[dimension]}
    b = {f"{dimension}:{token}" for dimension in DIMENSIONS for token in right[dimension]}
    return len(a & b) / max(1, len(a | b))


def diversity_screen(out: Path = DEFAULT_OUT) -> dict[str, object]:
    out = _safe_out(out)
    signatures = {case.task_id: _case_semantic(out / case.task_id, case) for case in CASES}
    pairs = []
    for index, left in enumerate(CASES):
        for right in CASES[index + 1:]:
            decisions = _pair_decision(signatures[left.task_id], signatures[right.task_id])
            aggregate = _aggregate_similarity(signatures[left.task_id], signatures[right.task_id])
            pairs.append({"left": left.task_id, "right": right.task_id, "dimensions": decisions, "aggregate_jaccard": aggregate, "aggregate_threshold": 0.97, "pass": all(row["pass"] for row in decisions.values()) and aggregate < 0.97})
    if len(pairs) != 780 or not all(row["pass"] for row in pairs):
        failed = next((row for row in pairs if not row["pass"]), None)
        _fail("duplicate_family", json.dumps(failed, sort_keys=True)[:1000])
    controls = {}
    base_signature = signatures[CASES[0].task_id]
    control_manifest = json.loads((out / ".state/adversarial-clone-controls/manifest.json").read_text())
    for name, item in control_manifest["controls"].items():
        root = _control_root(out, name)
        changed = [path for path in item["changed_files"] if (root / path).read_bytes() != (out / CASES[0].task_id / path).read_bytes()]
        if set(changed) != set(item["changed_files"]):
            _fail("clone_control_failed", f"{name}:unchanged")
        control_signature = _case_semantic(root, CASES[0], validate=False)
        decisions = _pair_decision(base_signature, control_signature)
        aggregate = _aggregate_similarity(base_signature, control_signature)
        rejected = not all(row["pass"] for row in decisions.values()) or aggregate >= 0.90
        if not rejected:
            _fail("clone_control_failed", name)
        controls[name] = {"changed_files": changed, "dimensions": decisions, "aggregate_jaccard": aggregate, "aggregate_threshold": 0.90, "production_rejected": True}
    result = {"schema_version": "integer-diversity-v2", "status": "pass", "root_count": 40, "pair_count": 780, "dimensions": list(DIMENSIONS), "normalizer": "emitted-artifact-token-bigrams-v2", "novelty_sources": ["docs", "header", "reference", "private-test", "coverage", "negative"], "pairs": pairs, "controls": controls}
    _write_json(out / ".state/diversity-screen.json", result)
    return result


def _semantic_tokens(text: str) -> set[str]:
    text = re.sub(r"`[^`]+`|\b\d+\b", " ", text.lower())
    stop = {"implement", "result", "valid", "member", "value", "witness", "input", "return", "bounded", "integer"}
    return {word for word in re.findall(r"[a-z_]{4,}", text) if word not in stop}


def _normalized_text(text: str, task_id: str) -> str:
    text = text.lower().replace(task_id, "task_symbol").replace(task_id.replace("-", "_"), "task_symbol")
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.M | re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '"literal"', text)
    text = re.sub(r"\b\d+\b", "number", text)
    return " ".join(re.findall(r"[a-z_]+|<=|>=|==|!=|&&|\|\||[<>%*/+-]", text))


def _surface_record(task_root: Path, task_id: str, label: str) -> dict[str, object] | None:
    config_path = task_root / ".meta/config.json"
    if not config_path.is_file():
        return None
    try:
        config = json.loads(config_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    files = config.get("files", {})
    solution = [task_root / path for path in files.get("solution", [])]
    examples = [task_root / path for path in files.get("example", [])]
    tests = [task_root / path for path in files.get("test", [])]
    if any(not path.is_file() for path in tests):
        normalized_tests: list[Path] = []
        for path in tests:
            if path.is_file():
                normalized_tests.append(path)
                continue
            root_relative = task_root / path.name
            if root_relative.is_file():
                normalized_tests.append(root_relative)
        discovered = sorted({*task_root.glob("*test*.cpp"), *(task_root / ".meta").glob("*test*.cpp")})
        tests = sorted({*normalized_tests, *(path for path in discovered if path.is_file())})
    docs = [path for path in sorted((task_root / ".docs").glob("*.md")) if path.is_file()]
    if not docs or not solution or not all(path.is_file() for path in [*solution, *examples, *tests]):
        return None
    def joined(paths: list[Path]) -> str:
        return "\n".join(path.read_text(errors="ignore") for path in paths)
    prompt = joined([*docs, *solution])
    api = joined([path for path in solution if path.suffix in {".h", ".hpp"}]) or joined(solution)
    reference = joined(examples)
    test_text = joined(tests) + ((task_root / "CMakeLists.txt").read_text(errors="ignore") if (task_root / "CMakeLists.txt").is_file() else "")
    provenance_path = task_root / ".meta/provenance.json"
    provenance = provenance_path.read_text(errors="ignore") if provenance_path.is_file() else ""
    surfaces = {"prompt": prompt, "api": api, "reference": reference, "tests": test_text, "lineage": provenance}
    hashes = {name: _sha(text.encode()) for name, text in surfaces.items()}
    normalized_hashes = {name: _sha(_normalized_text(text, task_id).encode()) for name, text in surfaces.items()}
    return {"label": label, "task_id": task_id, "hashes": hashes, "normalized_hashes": normalized_hashes, "semantic_tokens": sorted(_semantic_tokens(prompt + "\n" + api + "\n" + reference + "\n" + test_text))}


def _collect_contamination_inventory(
    out: Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    found = {path.name for path in HOLDOUT_ROOT.iterdir() if path.is_dir()} if HOLDOUT_ROOT.is_dir() else set()
    if found != OFFICIAL_HOLDOUTS:
        _fail("benchmark_screen_not_completed", f"found={len(found)}")
    inventory: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    for base, kind in [*((base, "existing") for base in EXISTING_ROOTS), (EXPANSION_ROOT, "expansion")]:
        if not base.is_dir():
            continue
        for config in base.rglob(".meta/config.json"):
            task_root = config.parent.parent
            if out.resolve() in task_root.resolve().parents or ".state" in task_root.parts:
                continue
            record = _surface_record(task_root, task_root.name, f"{kind}:{task_root.relative_to(REPO_ROOT)}")
            if not record:
                _fail("inventory_surface_missing", str(task_root.relative_to(REPO_ROOT)))
            inventory.append(record)
            sources.append({"kind": kind, "path": str(task_root.relative_to(REPO_ROOT)), "task_id": task_root.name})
    for slug in sorted(found):
        root = HOLDOUT_ROOT / slug
        record = _surface_record(root, slug, f"holdout:{slug}")
        if not record:
            _fail("benchmark_screen_not_completed", f"missing-role-surface:{slug}")
        inventory.append(record)
        sources.append({"kind": "holdout", "path": str(root.relative_to(REPO_ROOT)), "task_id": slug})
    inventory.sort(key=lambda row: str(row["label"]))
    sources.sort(key=lambda row: (str(row["kind"]), str(row["path"])))
    inventory_digest = _sha(json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode())
    source_digest = _sha(json.dumps(sources, sort_keys=True, separators=(",", ":")).encode())
    metadata = {
        "source_count": len(sources),
        "source_digest": source_digest,
        "surface_inventory_digest": inventory_digest,
    }
    return inventory, sources, metadata


def _inventory_revision(metadata: dict[str, object]) -> tuple[object, object, object]:
    return (
        metadata["source_count"],
        metadata["source_digest"],
        metadata["surface_inventory_digest"],
    )


def _contamination_screen(out: Path) -> dict[str, object]:
    _, _, before = _collect_contamination_inventory(out)
    inventory, sources, frozen = _collect_contamination_inventory(out)
    if _inventory_revision(before) != _inventory_revision(frozen):
        _fail(
            "inventory_unstable_before_screen",
            f"before={_inventory_revision(before)}:frozen={_inventory_revision(frozen)}",
        )
    comparisons = 0
    maximum = 0.0
    for case in CASES:
        candidate = _surface_record(out / case.task_id, case.task_id, f"candidate:{case.task_id}")
        if not candidate:
            _fail("prompt_contract_incomplete", case.task_id)
        for other in inventory:
            label = str(other["label"])
            exact_matches = []
            normalized_matches = []
            for surface in CONTAMINATION_SURFACES:
                if candidate["hashes"][surface] == other["hashes"][surface]:
                    exact_matches.append(surface)
                if candidate["normalized_hashes"][surface] == other["normalized_hashes"][surface]:
                    normalized_matches.append(surface)
            if "prompt" in exact_matches or "reference" in exact_matches or "tests" in exact_matches or {"prompt", "api", "reference"}.issubset(normalized_matches):
                _fail("benchmark_content_overlap" if label.startswith("holdout:") else "duplicate_family", f"{case.task_id}:{label}:exact={exact_matches}:normalized={normalized_matches}")
            candidate_tokens = set(candidate["semantic_tokens"])
            other_tokens = set(other["semantic_tokens"])
            score = len(candidate_tokens & other_tokens) / max(1, len(candidate_tokens | other_tokens))
            maximum = max(maximum, score)
            comparisons += 1
            if score >= 0.82:
                _fail("benchmark_content_overlap" if label.startswith("holdout:") else "duplicate_family", f"{case.task_id}:{label}:{score:.3f}")
    _, _, after = _collect_contamination_inventory(out)
    if _inventory_revision(frozen) != _inventory_revision(after):
        _fail(
            "inventory_changed_during_screen",
            f"frozen={_inventory_revision(frozen)}:after={_inventory_revision(after)}",
        )
    confirmations = {"before": before, "frozen": frozen, "after": after}
    _write_json(
        out / ".state/source-inventory.json",
        {
            "schema_version": "integer-source-inventory-v3",
            **frozen,
            "stable": True,
            "confirmations": confirmations,
            "sources": sources,
            "surface_records": inventory,
        },
    )
    result = {"status": "pass", "holdout_count": 26, **frozen, "inventory_stable": True, "inventory_confirmations": confirmations, "comparisons": comparisons, "surface_comparisons": comparisons * len(CONTAMINATION_SURFACES), "surfaces": list(CONTAMINATION_SURFACES), "max_jaccard": maximum, "normalizer": "integer-cross-corpus-v3-frozen"}
    _write_json(out / ".state/cross-corpus-screen.json", result)
    return result


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    out = _safe_out(out)
    manifest = json.loads((out / ".state/manifest.json").read_text())
    if manifest.get("task_ids") != [case.task_id for case in CASES] or manifest.get("task_count") != 40 or manifest.get("tree_hash") != _tree_hash(out):
        _fail("generator_output_drift", "manifest/tree")
    roles = [_role_check(out, case) for case in CASES]
    diversity = diversity_screen(out)
    contamination = _contamination_screen(out)
    collision = sorted(set(manifest["task_ids"]) & set(_existing_ids(exclude=out)))
    if collision:
        _fail("existing_task_id", ",".join(collision))
    receipt = {"schema_version": "integer-creator-preflight-v2", "status": "structural_pass_pending_runtime", "owner": OWNER, "owner_hash": _file_hash(REPO_ROOT / OWNER), "curriculum_hash": _file_hash(CURRICULUM), "remedy_spec_hash": _file_hash(REMEDY_SPEC), "focused_test_hash": _file_hash(REPO_ROOT / "tests/test_moonlight_integer_classification_number_theory_aider_tasks.py"), "tree_hash": _tree_hash(out), "root_count": 40, "prompt_role_count": len(roles), "diversity": {"pair_count": diversity["pair_count"], "normalizer": diversity["normalizer"], "receipt_hash": _file_hash(out / ".state/diversity-screen.json"), "status": "pass"}, "contamination": contamination, "source_inventory_hash": _file_hash(out / ".state/source-inventory.json"), "cross_corpus_screen_hash": _file_hash(out / ".state/cross-corpus-screen.json")}
    _write_json(out / ".state/creator-preflight.json", receipt)
    return receipt


def _replace_reference(root: Path) -> None:
    config = json.loads((root / ".meta/config.json").read_text())
    for target, example in zip(config["files"]["solution"], config["files"]["example"], strict=True):
        shutil.copy2(root / example, root / target)


def _runtime_one(root: Path, build_parent: Path, *, sanitizer: bool) -> int:
    work = build_parent / root.name
    shutil.copytree(root, work)
    _replace_reference(work)
    build = work / ("build-sanitizer" if sanitizer else "build-normal")
    command = ["cmake", "-S", str(work), "-B", str(build), "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=c++"]
    if sanitizer:
        command += ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]
    def checked(args: list[str], *, env: dict[str, str] | None = None) -> str:
        completed = subprocess.run(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if completed.returncode:
            _fail("runtime_command_failed", f"{root.name}:{'sanitizer' if sanitizer else 'normal'}:{' '.join(args)}\n{completed.stdout[-12000:]}")
        return completed.stdout

    checked(command)
    checked(["cmake", "--build", str(build), "-j2"])
    listing = subprocess.run(["ctest", "--test-dir", str(build), "-N"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout
    match = re.search(r"Total Tests: (\d+)", listing)
    count = int(match.group(1)) if match else 0
    env = os.environ.copy()
    if sanitizer:
        env["ASAN_OPTIONS"] = "detect_leaks=1:halt_on_error=1"
        env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
    checked(["ctest", "--test-dir", str(build), "--output-on-failure"], env=env)
    return count


def verify_runtime(out: Path = DEFAULT_OUT, *, evidence_class: str = "host_iteration") -> dict[str, object]:
    out = _safe_out(out)
    verify_core(out)
    roots = [("task", out / case.task_id) for case in CASES]
    roots += [("control", _control_root(out, name)) for name in ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection")]
    records = []
    with tempfile.TemporaryDirectory(prefix="integer-number-theory-") as temp:
        scratch = Path(temp)
        for kind, root in roots:
            normal = _runtime_one(root, scratch / "normal", sanitizer=False)
            sanitizer = _runtime_one(root, scratch / "sanitizer", sanitizer=True)
            if normal <= 0 or normal != sanitizer:
                _fail("sanitizer_test_count_mismatch", f"{root.name}:{normal}:{sanitizer}")
            records.append({"kind": kind, "task_id": root.name, "normal": normal, "sanitizer": sanitizer, "negative_compiled": True, "negative_smoke_passed": True, "negative_rejected": True})
    compiler_path = shutil.which("c++") or "c++"
    compiler = subprocess.run([compiler_path, "--version"], check=True, text=True, stdout=subprocess.PIPE).stdout.splitlines()[0]
    cmake = subprocess.run(["cmake", "--version"], check=True, text=True, stdout=subprocess.PIPE).stdout.splitlines()[0]
    receipt = {"schema_version": "integer-runtime-v1", "status": "pass", "evidence_class": evidence_class, "locked_oracle": False, "network_policy": "none" if evidence_class == "docker_sanity" else "host", "tree_hash": _tree_hash(out), "owner_hash": _file_hash(REPO_ROOT / OWNER), "root_count": 40, "control_count": 3, "normal_test_count_per_root": 4, "sanitizer_test_count_per_root": 4, "compiler": {"path": compiler_path, "version": compiler, "sha256": _file_hash(Path(compiler_path))}, "cmake": cmake, "records": records}
    _write_json(out / ".state/runtime.json", receipt)
    return receipt


def docker_sanity(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> dict[str, object]:
    out = _safe_out(out)
    verify_core(out)
    inspected = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if inspected.returncode:
        _fail("docker_sanity_not_completed", inspected.stderr.strip())
    before = _tree_hash(out)
    command = ["docker", "run", "--rm", "--network", "none", "-v", f"{REPO_ROOT}:{REPO_ROOT}:ro", "-v", f"{out}:{out}:rw", "-e", f"PYTHONPATH={REPO_ROOT / 'src'}", "-w", str(REPO_ROOT), image, "python3", "-m", "w8_biayn.integrations.moonlight_integer_classification_number_theory_aider_tasks", "--out", str(out), "--verify-runtime", "--docker-runtime"]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode:
        _fail("docker_sanity_failed", completed.stdout[-16000:])
    runtime = json.loads((out / ".state/runtime.json").read_text())
    if runtime["tree_hash"] != before or _tree_hash(out) != before:
        _fail("grader_mount_hash_mismatch", f"{before}:{runtime['tree_hash']}:{_tree_hash(out)}")
    runtime.update({"evidence_class": "docker_sanity", "network_policy": "none", "image": image, "image_id": inspected.stdout.strip(), "docker_command": command})
    _write_json(out / ".state/docker-sanity.json", runtime)
    manifest = json.loads((out / ".state/manifest.json").read_text())
    manifest.update({"status": "creator_preflight_pass_pending_independent_audit", "docker_receipt": ".state/docker-sanity.json"})
    _write_json(out / ".state/manifest.json", manifest)
    for case in CASES:
        remedy_path = out / ".state/remedy" / f"{case.task_id}.json"
        remedy = json.loads(remedy_path.read_text())
        _write_json(out / ".state/remedy-verification" / f"{case.task_id}.json", {"schema_version": "aider-task-remedy-verification-v1", "task_id": case.task_id, "status": "verified_pending_fresh_audit", "remedy_record_hash": _file_hash(remedy_path), "tree_hash_after": _tree_hash(out / case.task_id), "generator_revision": remedy["generator_revision"], "benchmark_screen": "pass", "docker_receipt": ".state/docker-sanity.json", "docker_receipt_hash": _file_hash(out / ".state/docker-sanity.json")})
    return runtime


def _append_cycle(out: Path, state: str, **extra: object) -> None:
    path = out / ".state/cycles.jsonl"
    record = {"schema_version": "aider-task-creation-cycle-v1", "cycle": sum(1 for _ in path.open()) + 1 if path.exists() else 1, "state": state, "family_id": FAMILY_ID, "tree_hash": _tree_hash(out), "owner_hash": _file_hash(REPO_ROOT / OWNER), **extra}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--materialize", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-runtime", action="store_true")
    parser.add_argument("--docker-runtime", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--creator-preflight", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.materialize:
        materialize(args.out, force=args.force)
        _append_cycle(args.out, "generating")
    if args.verify_core:
        verify_core(args.out)
    if args.verify_runtime:
        verify_runtime(args.out, evidence_class="docker_sanity" if args.docker_runtime else "host_iteration")
    if args.docker_sanity or args.creator_preflight:
        docker_sanity(args.out, args.image)
        _append_cycle(args.out, "creator_preflight")
    if not any((args.materialize, args.verify_core, args.verify_runtime, args.docker_sanity, args.creator_preflight)):
        print(json.dumps(materialize(args.out), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
