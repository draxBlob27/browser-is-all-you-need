"""Executable contracts for the lexical-canonicalization expansion family.

The owner renders these contracts into independent task roots.  The ten bands
use different parser state and value models; the ten profiles inside each band
add a different semantic invariant and deliberately-wrong implementation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Contract:
    band: str
    profile: str
    public_contract: str
    valid_input: str
    canonical: str
    named_invalid: str
    other_invalid: tuple[str, ...]
    valid_variants: tuple[tuple[str, str], ...]
    source: str
    negative_source: str
    api_extra: str
    success_assignments: str
    result_contract: str
    detail_assertion: str
    features: dict[str, tuple[str, ...]]


PROFILE_NAMES = (
    "rolling-checksum",
    "reserved-token",
    "strictly-increasing",
    "unique-symbols",
    "bounded-value",
    "required-class",
    "parity-invariant",
    "leading-symbol",
    "cross-field-disjointness",
    "optional-branch-completeness",
)

BANDS = (
    "fixed-state-identifier",
    "hierarchical-locator",
    "escaped-quoted-atom",
    "numeric-lexeme",
    "version-release-token",
    "path-namespace-token",
    "unit-bearing-value",
    "ordered-range-list",
    "tagged-mini-record",
    "length-framed-input",
)

PROFILE_API_EXTRAS = (
    "int checksum_remainder = 0;",
    "std::string approval_word;",
    "std::size_t increasing_digit_count = 0;",
    "std::size_t unique_symbol_count = 0;",
    "int bounded_witness = 0;",
    "std::size_t required_digit_index = 0;",
    "bool parity_even = false;",
    "char leading_symbol = '\\0';",
    "bool witness_disjoint = false;",
    "std::string optional_value;",
)

BAND_API_EXTRAS = (
    "unsigned identifier_hyphen_count = 0;",
    "std::array<std::size_t, 1> locator_slash_count{0};",
    "int decoded_atom_bytes = 0;",
    "long mantissa_digit_count = 0;",
    "std::size_t version_component_count = 0;",
    "std::vector<std::size_t> normalized_segment_count;",
    "std::pair<std::size_t, std::size_t> unit_symbol_count{0, 0};",
    "std::optional<std::size_t> range_count;",
    "std::map<std::string, std::size_t> record_field_count;",
    "long long declared_payload_bytes = 0;",
)

BAND_SUCCESS = (
    "result.identifier_hyphen_count = static_cast<unsigned>(count_char(base, '-'));",
    "result.locator_slash_count = {count_char(base, '/')};",
    "result.decoded_atom_bytes = static_cast<int>(base.find(\"\\\\n\") - 1U);",
    "result.mantissa_digit_count = static_cast<long>(count_digits(base.substr(0, base.find(':'))));",
    "result.version_component_count = 3U;",
    "result.normalized_segment_count = {count_char(base, '/') + 1U};",
    "result.unit_symbol_count = {between_size(base, '[', ']'), 2U};",
    "result.range_count = count_char(base.substr(0, base.find(']')), ',') + 1U;",
    "result.record_field_count = {{\"N\", 1U}, {\"TAG\", 1U}};",
    "result.declared_payload_bytes = static_cast<long long>(to_int(base.substr(0, base.find(':'))));",
)

PROFILE_RESULT_CONTRACTS = (
    "`checksum_remainder` is the decimal value after `#`.",
    "`approval_word` is the uppercase word after `!`.",
    "`increasing_digit_count` counts decimal digits after `^`.",
    "`unique_symbol_count` counts uppercase symbols after `%`.",
    "`bounded_witness` is the decimal value inside the final brackets.",
    "`required_digit_index` is the zero-based index of the first digit after `+`.",
    "`parity_even` is true exactly when the final parity marker is `E`.",
    "`leading_symbol` is the uppercase byte after `@`.",
    "`witness_disjoint` is true after the `/` witness is proved disjoint from the primary decimal field.",
    "`optional_value` is the nonempty uppercase value after `?`.",
)

BAND_RESULT_CONTRACTS = (
    "`identifier_hyphen_count` counts hyphens before the dialect suffix.",
    "`locator_slash_count[0]` counts locator slashes before the dialect suffix.",
    "`decoded_atom_bytes` counts decoded atom bytes before the `\\n` escape.",
    "`mantissa_digit_count` counts decimal digits in the numeric lexeme before the colon.",
    "`version_component_count` is exactly three for a successful version.",
    "`normalized_segment_count` contains one value: the surviving path-segment count.",
    "`unit_symbol_count` stores unit-symbol count followed by the required fractional precision (two).",
    "`range_count` contains the canonical list-item count.",
    "`record_field_count` maps `N` and `TAG` to their unique occurrence count (one each).",
    "`declared_payload_bytes` is the parsed frame length.",
)


def _features(band: int, pos: int) -> dict[str, tuple[str, ...]]:
    band_name = BANDS[band]
    profile = PROFILE_NAMES[pos]
    return {
        "public_api": (f"payload-layout-{pos}", f"band-value-{band_name}"),
        "owned_state_or_algorithm": (band_name, profile, f"state-composition-{band}-{pos}"),
        "mutation_or_selection_rules": (f"canonicalizer-{band_name}", f"semantic-rule-{profile}"),
        "invalid_and_boundary_behavior": (f"invalid-{profile}", f"eoi-{band_name}"),
        "reference_control_flow": (f"parser-{band_name}", f"guard-{profile}", f"flow-{band}-{pos}"),
        "deterministic_oracle": (f"oracle-{band_name}-{profile}", f"mutation-map-{band}-{pos}"),
        "topic_specific_negative_fixture": (f"negative-{band_name}-{profile}",),
    }


def _wrap(body: str, negative_body: str, *, band: int, pos: int, contract: str,
          valid: str, canonical: str, invalid: str, other: tuple[str, ...],
          detail_assertion: str,
          valid_variants: tuple[tuple[str, str], ...] = ()) -> Contract:
    delimiter = "#!^%[+=@/?"[pos]
    profile_success = (
        "result.checksum_remainder = to_int(tail);",
        "result.approval_word = tail;",
        "result.increasing_digit_count = count_digits(tail);",
        "result.unique_symbol_count = tail.size();",
        "result.bounded_witness = to_int(tail);",
        "result.required_digit_index = first_digit_index(tail);",
        "result.parity_even = tail == \"E\";",
        "result.leading_symbol = tail.front();",
        "result.witness_disjoint = true;",
        "result.optional_value = tail;",
    )[pos]
    return Contract(
        band=BANDS[band],
        profile=PROFILE_NAMES[pos],
        public_contract=contract,
        valid_input=valid,
        canonical=canonical,
        named_invalid=invalid,
        other_invalid=other,
        valid_variants=valid_variants,
        source=body,
        negative_source=negative_body,
        api_extra=BAND_API_EXTRAS[band] + " " + PROFILE_API_EXTRAS[pos],
        success_assignments=(
            f"const auto suffix = result.canonical.rfind('{delimiter}'); "
            "const std::string base = result.canonical.substr(0, suffix); "
            "std::string tail = result.canonical.substr(suffix + 1U); "
            "if (!tail.empty() && tail.back() == ';') tail.pop_back(); "
            "if (!tail.empty() && tail.back() == ']') tail.pop_back(); "
            + BAND_SUCCESS[band] + " " + profile_success
        ),
        result_contract=BAND_RESULT_CONTRACTS[band] + " " + PROFILE_RESULT_CONTRACTS[pos],
        detail_assertion=detail_assertion,
        features=_features(band, pos),
    )


def _dialect(pos: int, *, number: str) -> tuple[str, str, str, str, str, str, str]:
    """Return valid/canonical/invalid suffixes, parser bodies, prose, and assertion."""
    valid = ("#7;", "!ok;", "^147;", "%abc;", "[42];", "+a1;", "=E;", "@a;", "/zx;", "?ok;")[pos]
    canonical = ("#7;", "!OK;", "^147;", "%ABC;", "[42];", "+A1;", "=E;", "@A;", "/ZX;", "?OK;")[pos]
    invalid = ("#8;", "!BAD;", "^132;", "%ABA;", "[9];", "+AB;", "=O;", "@2;", "/X7;", "?;")[pos]
    prose = (
        "a mandatory `#d` checksum witness equal to decimal digit-sum modulo ten",
        "a mandatory `!word` approval witness whose uppercase spelling may not be `BAD`",
        "a mandatory `^digits` witness with strictly increasing decimal digits",
        "a mandatory `%symbols` witness of nonempty ASCII alphanumerics whose uppercase bytes are pairwise unique",
        "a mandatory `[decimal]` witness in the inclusive range 10 through 9000",
        "a mandatory `+token` witness of nonempty ASCII alphanumerics containing at least one ASCII digit",
        "a mandatory `=E` or `=O` marker matching the primary decimal field's parity",
        "a mandatory `@byte` witness that is one ASCII letter",
        "a mandatory `/token` witness of nonempty ASCII alphanumerics sharing no byte with the primary decimal field",
        "a mandatory `?value` optional branch with a nonempty alphanumeric value",
    )[pos]
    parsers = (
        f"if(p>=input.size()||input[p]!='#')return fail(p,\"checksum marker\");++p;std::string witness;if(p<input.size()&&ascii_digit(input[p]))witness.push_back(input[p++]);if(witness.size()!=1U)return fail(p,\"checksum digit\");if(p!=input.size())return fail(p,\"trailing input\");if(to_int(witness)!=(digit_sum({number})%10))return fail(p,\"checksum mismatch\");",
        "if(p>=input.size()||input[p]!='!')return fail(p,\"approval marker\");++p;std::string witness;while(p<input.size()&&ascii_alpha(input[p]))witness.push_back(upper(input[p++]));if(witness.empty())return fail(p,\"approval word\");if(p!=input.size())return fail(p,\"trailing input\");if(witness==\"BAD\")return fail(p,\"reserved approval\");",
        "if(p>=input.size()||input[p]!='^')return fail(p,\"sequence marker\");++p;std::string witness;while(p<input.size()&&ascii_digit(input[p]))witness.push_back(input[p++]);if(witness.empty())return fail(p,\"digit witness\");if(p!=input.size())return fail(p,\"trailing input\");if(!strictly_increasing(witness))return fail(p,\"not increasing\");",
        "if(p>=input.size()||input[p]!='%')return fail(p,\"unique marker\");++p;std::string witness;while(p<input.size()&&ascii_alnum(input[p]))witness.push_back(upper(input[p++]));if(witness.empty())return fail(p,\"symbol witness\");if(p!=input.size())return fail(p,\"trailing input\");if(!all_unique(witness))return fail(p,\"duplicate symbol\");",
        "if(p>=input.size()||input[p]!='[')return fail(p,\"bound open\");++p;std::string witness;while(p<input.size()&&ascii_digit(input[p]))witness.push_back(input[p++]);if(witness.empty())return fail(p,\"bound value\");if(p>=input.size()||input[p]!=']')return fail(p,\"bound close\");++p;if(p!=input.size())return fail(p,\"trailing input\");if(to_int(witness)<10||to_int(witness)>9000)return fail(p,\"bound range\");",
        "if(p>=input.size()||input[p]!='+')return fail(p,\"class marker\");++p;std::string witness;while(p<input.size()&&ascii_alnum(input[p]))witness.push_back(upper(input[p++]));if(witness.empty())return fail(p,\"class witness\");if(p!=input.size())return fail(p,\"trailing input\");if(!contains_digit(witness))return fail(p,\"digit required\");",
        f"if(p>=input.size()||input[p]!='=')return fail(p,\"parity marker\");++p;std::string witness;if(p<input.size()&&(input[p]=='E'||input[p]=='O'))witness.push_back(input[p++]);if(witness.empty())return fail(p,\"parity value\");if(p!=input.size())return fail(p,\"trailing input\");if(((to_int({number})%2)==0)!=(witness==\"E\"))return fail(p,\"parity mismatch\");",
        "if(p>=input.size()||input[p]!='@')return fail(p,\"leading marker\");++p;std::string witness;if(p<input.size())witness.push_back(upper(input[p++]));if(witness.empty())return fail(p,\"leading witness\");if(p!=input.size())return fail(p,\"trailing input\");if(!ascii_alpha(witness.front()))return fail(p,\"letter required\");",
        f"if(p>=input.size()||input[p]!='/')return fail(p,\"disjoint marker\");++p;std::string witness;while(p<input.size()&&ascii_alnum(input[p]))witness.push_back(upper(input[p++]));if(witness.empty())return fail(p,\"disjoint witness\");if(p!=input.size())return fail(p,\"trailing input\");if(shares_symbol({number},witness))return fail(p,\"fields overlap\");",
        "if(p>=input.size()||input[p]!='?')return fail(p,\"optional marker\");++p;std::string witness;while(p<input.size()&&ascii_alnum(input[p]))witness.push_back(upper(input[p++]));if(p!=input.size())return fail(p,\"trailing input\");if(witness.empty())return fail(p,\"incomplete optional branch\");",
    )
    wrong = (
        f"if(p>=input.size()||input[p]!='#')return fail(p,\"checksum marker\");++p;std::string witness;if(p<input.size()&&ascii_digit(input[p]))witness.push_back(input[p++]);if(witness.size()!=1U)return fail(p,\"checksum digit\");if(p!=input.size())return fail(p,\"trailing input\");if(to_int(witness)==((digit_sum({number})+2)%10))return fail(p,\"wrong checksum\");",
        "if(p>=input.size()||input[p]!='!')return fail(p,\"approval marker\");++p;std::string witness;while(p<input.size()&&ascii_alpha(input[p]))witness.push_back(upper(input[p++]));if(witness.empty())return fail(p,\"approval word\");if(p!=input.size())return fail(p,\"trailing input\");if(witness.size()==4U&&witness.front()=='V')return fail(p,\"wrong reserved approval\");",
        "if(p>=input.size()||input[p]!='^')return fail(p,\"sequence marker\");++p;std::string witness;while(p<input.size()&&ascii_digit(input[p]))witness.push_back(input[p++]);if(witness.empty())return fail(p,\"digit witness\");if(p!=input.size())return fail(p,\"trailing input\");",
        "if(p>=input.size()||input[p]!='%')return fail(p,\"unique marker\");++p;std::string witness;while(p<input.size()&&ascii_alnum(input[p]))witness.push_back(upper(input[p++]));if(witness.size()<2U)return fail(p,\"length only\");if(p!=input.size())return fail(p,\"trailing input\");",
        "if(p>=input.size()||input[p]!='[')return fail(p,\"bound open\");++p;std::string witness;while(p<input.size()&&ascii_digit(input[p]))witness.push_back(input[p++]);if(witness.empty())return fail(p,\"bound value\");if(p>=input.size()||input[p]!=']')return fail(p,\"bound close\");++p;if(p!=input.size())return fail(p,\"trailing input\");",
        "if(p>=input.size()||input[p]!='+')return fail(p,\"class marker\");++p;std::string witness;while(p<input.size()&&ascii_alnum(input[p]))witness.push_back(upper(input[p++]));if(witness.empty())return fail(p,\"class witness\");if(p!=input.size())return fail(p,\"trailing input\");",
        f"if(p>=input.size()||input[p]!='=')return fail(p,\"parity marker\");++p;std::string witness;if(p<input.size()&&(input[p]=='E'||input[p]=='O'))witness.push_back(input[p++]);if(witness.empty())return fail(p,\"parity value\");if(p!=input.size())return fail(p,\"trailing input\");if(to_int({number})==0)return fail(p,\"nonzero only\");",
        "if(p>=input.size()||input[p]!='@')return fail(p,\"leading marker\");++p;std::string witness;if(p<input.size())witness.push_back(upper(input[p++]));if(witness.empty())return fail(p,\"leading witness\");if(p!=input.size())return fail(p,\"trailing input\");if(!ascii_alnum(witness.front()))return fail(p,\"alnum only\");",
        f"if(p>=input.size()||input[p]!='/')return fail(p,\"disjoint marker\");++p;std::string witness;while(p<input.size()&&ascii_alnum(input[p]))witness.push_back(upper(input[p++]));if(witness.empty())return fail(p,\"disjoint witness\");if(p!=input.size())return fail(p,\"trailing input\");if(!{number}.empty()&&{number}.front()==witness.front())return fail(p,\"first only\");",
        "if(p>=input.size()||input[p]!='?')return fail(p,\"optional marker\");++p;std::string witness;while(p<input.size()&&ascii_alnum(input[p]))witness.push_back(upper(input[p++]));if(p!=input.size())return fail(p,\"trailing input\");if(witness==\"??\")return fail(p,\"double marker only\");",
    )[pos]
    terminal = (
        "if(p>=input.size()||input[p]!=';')return fail(p,\"terminal semicolon\");"
        "++p;if(p!=input.size())return fail(p,\"trailing input\");"
    )
    eoi = 'if(p!=input.size())return fail(p,"trailing input");'
    parser = parsers[pos].replace(eoi, terminal)
    wrong = wrong.replace(eoi, terminal)
    assertions = (
        "a.checksum_remainder==7",
        'a.approval_word=="OK"',
        "a.increasing_digit_count==3U",
        "a.unique_symbol_count==3U",
        "a.bounded_witness==42",
        "a.required_digit_index==1U",
        "a.parity_even",
        "a.leading_symbol=='A'",
        "a.witness_disjoint",
        'a.optional_value=="OK"',
    )[pos]
    return valid, canonical, invalid, parser, wrong, prose + ", terminated by `;`", assertions


def _tail_render(pos: int) -> str:
    return (
        '+"#"+witness+";"', '+"!"+witness+";"', '+"^"+witness+";"', '+"%"+witness+";"',
        '+"["+witness+"];"', '+"+"+witness+";"', '+"="+witness+";"', '+"@"+witness+";"',
        '+"/"+witness+";"', '+"?"+witness+";"',
    )[pos]


COMMON_HELPERS = r'''
[[maybe_unused]] bool ascii_alpha(char c){return (c>='A'&&c<='Z')||(c>='a'&&c<='z');}
[[maybe_unused]] bool ascii_digit(char c){return c>='0'&&c<='9';}
[[maybe_unused]] bool ascii_alnum(char c){return ascii_alpha(c)||ascii_digit(c);}
[[maybe_unused]] char upper(char c){return c>='a'&&c<='z'?static_cast<char>(c-'a'+'A'):c;}
[[maybe_unused]] char lower(char c){return c>='A'&&c<='Z'?static_cast<char>(c-'A'+'a'):c;}
[[maybe_unused]] int to_int(const std::string& s){int v=0;for(char c:s){if(!ascii_digit(c))continue;int d=c-'0';if(v>(std::numeric_limits<int>::max()-d)/10)return std::numeric_limits<int>::max();v=v*10+d;}return v;}
[[maybe_unused]] int digit_sum(const std::string& s){int v=0;for(char c:s){if(ascii_digit(c))v+=c-'0';}return v;}
[[maybe_unused]] bool strictly_increasing(const std::string& s){char previous=0;bool seen=false;for(char c:s){if(!ascii_digit(c))continue;if(seen&&c<=previous)return false;previous=c;seen=true;}return seen;}
[[maybe_unused]] bool all_unique(const std::string& s){for(std::size_t i=0;i<s.size();++i)for(std::size_t j=i+1;j<s.size();++j)if(s[i]==s[j])return false;return true;}
[[maybe_unused]] bool contains_digit(const std::string& s){for(char c:s)if(ascii_digit(c))return true;return false;}
[[maybe_unused]] bool shares_symbol(const std::string& a,const std::string& b){for(char x:a)for(char y:b)if(x==y)return true;return false;}
[[maybe_unused]] bool all_digits(const std::string& s){if(s.empty())return false;for(char c:s)if(!ascii_digit(c))return false;return true;}
[[maybe_unused]] bool all_alnum(const std::string& s){if(s.empty())return false;for(char c:s)if(!ascii_alnum(c))return false;return true;}
[[maybe_unused]] std::size_t count_char(const std::string& s,char wanted){std::size_t n=0;for(char c:s)if(c==wanted)++n;return n;}
[[maybe_unused]] std::size_t count_digits(const std::string& s){std::size_t n=0;for(char c:s)if(ascii_digit(c))++n;return n;}
[[maybe_unused]] std::size_t first_digit_index(const std::string& s){for(std::size_t i=0;i<s.size();++i)if(ascii_digit(s[i]))return i;return s.size();}
[[maybe_unused]] std::size_t between_size(const std::string& s,char open,char close){auto a=s.find(open);auto b=s.find(close,a==std::string::npos?0U:a+1U);return a==std::string::npos||b==std::string::npos||b<=a?0U:b-a-1U;}
'''


def _fixed(task_id: str, pos: int, prefix: str) -> Contract:
    sep = "-"
    numbers = ("34", "14", "147", "123", "42", "26", "24", "68", "57", "84")
    tags = ("X9", "OK", "AZ", "ABC", "Q7", "A1", "R8", "A2", "ZX", "K4")
    number, tag = numbers[pos], tags[pos]
    if pos == 0:
        number = "34"  # sum 7
    suffix, canonical_suffix, bad_suffix, tail, wrong_tail, prose, detail = _dialect(pos, number="number")
    base_valid = f"{prefix.lower()}{sep}{number}{sep}{tag.lower()}"
    base_canonical = f"{prefix}{sep}{number}{sep}{tag}"
    valid, canonical, invalid = base_valid + suffix, base_canonical + canonical_suffix, base_canonical + bad_suffix
    template = r'''
std::size_t p=0;const std::string expected="@PREFIX@";std::string prefix;
for(char want:expected){if(p>=input.size()||upper(input[p])!=want)return fail(p,"prefix");prefix.push_back(want);++p;}
if(p>=input.size()||input[p]!='-')return fail(p,"first separator");++p;
std::string number;while(p<input.size()&&ascii_digit(input[p]))number.push_back(input[p++]);
if(number.size()<2U||number.size()>4U)return fail(p,"number width");
if(p>=input.size()||input[p]!='-')return fail(p,"second separator");++p;
std::string tag;while(p<input.size()&&ascii_alnum(input[p]))tag.push_back(upper(input[p++]));
if(tag.size()<2U||tag.size()>3U)return fail(p,"tag width");
@TAIL@
return pass(prefix+"-"+number+"-"+tag@RENDER@,p);
'''
    body = template.replace("@PREFIX@", prefix).replace("@TAIL@", tail).replace("@RENDER@", _tail_render(pos))
    neg = template.replace("@PREFIX@", prefix).replace("@TAIL@", wrong_tail).replace("@RENDER@", _tail_render(pos))
    contract = f"Recognize `{prefix}-<2..4 digits>-<2..3 alphanumerics>` case-insensitively, render uppercase fields, then parse {prose}. Every byte must be consumed."
    return _wrap(body, neg, band=0, pos=pos, contract=contract, valid=valid,
                 canonical=canonical, invalid=invalid,
                 other=("", base_canonical, canonical + "!", prefix + "/" + number + "-" + tag),
                 detail_assertion=f"a.identifier_hyphen_count==2U&&({detail})")


def _locator(task_id: str, pos: int, prefix: str) -> Contract:
    numbers = ("34", "14", "147", "123", "42", "26", "24", "68", "57", "84")
    tags = ("X9", "OK", "AZ", "ABC", "Q7", "A1", "R8", "A2", "ZX", "K4")
    number, tag = numbers[pos], tags[pos]
    suffix, canonical_suffix, bad_suffix, tail, wrong_tail, prose, detail = _dialect(pos, number="number")
    base_valid = f"{prefix.lower()}/{number}/{tag.lower()}.1"
    base_canonical = f"{prefix}/{number}/{tag}.1"
    valid, canonical, invalid = base_valid + suffix, base_canonical + canonical_suffix, base_canonical + bad_suffix
    template = r'''
std::size_t p=0;const std::string expected="@PREFIX@";std::string head;
for(char want:expected){if(p>=input.size()||upper(input[p])!=want)return fail(p,"locator head");head.push_back(want);++p;}
if(p>=input.size()||input[p++]!='/')return fail(p,"slash one");std::string number;
while(p<input.size()&&ascii_digit(input[p]))number.push_back(input[p++]);if(number.empty())return fail(p,"missing bay");
if(p>=input.size()||input[p++]!='/')return fail(p,"slash two");std::string tag;
while(p<input.size()&&ascii_alnum(input[p]))tag.push_back(upper(input[p++]));if(tag.empty())return fail(p,"missing cell");
if(p>=input.size()||input[p]!='.')return fail(p,"revision dot");++p;std::string revision;
while(p<input.size()&&ascii_digit(input[p]))revision.push_back(input[p++]);if(revision.empty()||to_int(revision)<=0)return fail(p,"positive revision");
@TAIL@
return pass(head+"/"+number+"/"+tag+"."+revision@RENDER@,p);
'''
    body = template.replace("@PREFIX@", prefix).replace("@TAIL@", tail).replace("@RENDER@", _tail_render(pos))
    neg = template.replace("@PREFIX@", prefix).replace("@TAIL@", wrong_tail).replace("@RENDER@", _tail_render(pos))
    return _wrap(body, neg, band=1, pos=pos,
                 contract=f"Parse the hierarchical locator `{prefix}/<bay>/<cell>.<positive-revision>`, uppercase its symbolic fields, then parse {prose}; no prefix parse is accepted.",
                 valid=valid, canonical=canonical, invalid=invalid,
                 other=("", base_canonical, f"{prefix}/{number}/{tag}.0" + canonical_suffix, canonical + "!", prefix + "//" + tag + ".1"),
                 detail_assertion=f"a.locator_slash_count[0]==2U&&({detail})")


def _quoted(task_id: str, pos: int, prefix: str) -> Contract:
    raw_values = ("a3d", "okay", "147", "abc", "q7", "a1", "r8", "a2", "zx", "k4")
    text = raw_values[pos]
    number = ("34", "14", "147", "123", "42", "26", "24", "68", "57", "84")[pos]
    if pos == 0:
        text = "a3c"  # digit sum through the auxiliary number below is seven
    suffix, canonical_suffix, bad_suffix, tail, wrong_tail, prose, detail = _dialect(pos, number="number")
    base_valid = f'"{text}\\n{number}"'
    base_canonical = f'"{text.upper()}\\n{number}"'
    escaped_valid = f'"a\\\\b\\"c\\n{number}"'
    escaped_canonical = f'"A\\\\B\\"C\\n{number}"'
    valid, canonical, invalid = base_valid + suffix, base_canonical + canonical_suffix, base_canonical + bad_suffix
    template = r'''
std::size_t p=0;if(p>=input.size()||input[p]!='"')return fail(p,"opening quote");++p;std::string text;std::string number;bool after_newline=false;
while(p<input.size()&&input[p]!='"'){char c=input[p++];if(c=='\\'){if(p>=input.size())return fail(p,"dangling escape");char e=input[p++];if(e=='n'){if(after_newline)return fail(p,"second newline escape");after_newline=true;continue;}if(e!='\\'&&e!='"')return fail(p,"escape");c=e;}if(after_newline){if(!ascii_digit(c))return fail(p-1U,"decimal tail");number.push_back(c);}else{if(!ascii_alnum(c)&&c!='\\'&&c!='"')return fail(p-1U,"quoted atom");text.push_back(upper(c));}}
if(p>=input.size()||input[p]!='"')return fail(p,"closing quote");++p;if(text.empty()||number.empty())return fail(p,"missing quoted field");
@TAIL@
std::string encoded;for(char c:text){if(c=='\\'||c=='"')encoded.push_back('\\');encoded.push_back(c);}return pass("\""+encoded+"\\n"+number+"\""@RENDER@,p);
'''
    body = template.replace("@TAIL@", tail).replace("@RENDER@", _tail_render(pos))
    neg = template.replace("@TAIL@", wrong_tail).replace("@RENDER@", _tail_render(pos))
    return _wrap(body, neg, band=2, pos=pos,
                 contract=f"Scan one quoted atom with `\\\\`, `\\\"`, and exactly one `\\n` escape; uppercase the nonempty pre-newline alphanumeric atom, require a nonempty decimal tail, close the quote, then parse {prose}.",
                 valid=valid, canonical=canonical, invalid=invalid,
                 other=("", base_canonical, canonical + "x", '"unterminated\\', '"A\\n12x"' + canonical_suffix),
                 detail_assertion=f"a.decoded_atom_bytes=={len(text)}&&({detail})",
                 valid_variants=((escaped_valid + suffix, escaped_canonical + canonical_suffix),))


def _numeric(task_id: str, pos: int, prefix: str) -> Contract:
    numbers = ("34", "14", "147", "123", "42", "26", "24", "68", "57", "84")
    tags = ("X9", "OK", "AZ", "ABC", "Q7", "A1", "R8", "A2", "ZX", "K4")
    number, tag = numbers[pos], tags[pos]
    suffix, canonical_suffix, bad_suffix, tail, wrong_tail, prose, detail = _dialect(pos, number="whole")
    base_valid = f"+{number}.{pos + 10:02d}e+2:{tag.lower()}"
    base_canonical = f"{number}.{pos + 10:02d}e2:{tag}"
    valid, canonical, invalid = base_valid + suffix, base_canonical + canonical_suffix, base_canonical + bad_suffix
    template = r'''
std::size_t p=0;bool negative=false;if(p<input.size()&&(input[p]=='+'||input[p]=='-')){negative=input[p]=='-';++p;}std::string whole;
while(p<input.size()&&ascii_digit(input[p]))whole.push_back(input[p++]);if(whole.empty())return fail(p,"whole part");if(p>=input.size()||input[p++]!='.')return fail(p,"decimal point");std::string fraction;
while(p<input.size()&&ascii_digit(input[p]))fraction.push_back(input[p++]);if(fraction.size()!=2U)return fail(p,"fraction width");if(p>=input.size()||lower(input[p++])!='e')return fail(p,"exponent marker");
std::string exponent_sign;if(p<input.size()&&(input[p]=='+'||input[p]=='-')){if(input[p]=='-')exponent_sign="-";++p;}std::string exponent;while(p<input.size()&&ascii_digit(input[p]))exponent.push_back(input[p++]);if(exponent.empty())return fail(p,"exponent");if(p>=input.size()||input[p]!=':')return fail(p,"unit separator");++p;std::string tag;
while(p<input.size()&&ascii_alnum(input[p]))tag.push_back(upper(input[p++]));if(tag.empty())return fail(p,"unit");
@TAIL@
std::string sign=negative?"-":"";return pass(sign+whole+"."+fraction+"e"+exponent_sign+exponent+":"+tag@RENDER@,p);
'''
    body = template.replace("@TAIL@", tail).replace("@RENDER@", _tail_render(pos))
    neg = template.replace("@TAIL@", wrong_tail).replace("@RENDER@", _tail_render(pos))
    return _wrap(body, neg, band=3, pos=pos,
                 contract=f"Recognize a signed fixed-decimal scientific lexeme followed by a colon unit, remove positive signs, preserve a negative exponent sign, uppercase the unit, then parse {prose}.",
                 valid=valid, canonical=canonical, invalid=invalid,
                 other=("", base_canonical, canonical + "!", number + ".00e:" + tag, f"{number}.10e-2:{tag}"),
                 detail_assertion=f"a.mantissa_digit_count=={len(number) + 3}L&&({detail})")


def _version(task_id: str, pos: int, prefix: str) -> Contract:
    numbers = ("34", "14", "147", "123", "42", "26", "24", "68", "57", "84")
    tags = ("X9", "OK", "AZ", "ABC", "Q7", "A1", "R8", "A2", "ZX", "K4")
    number, tag = numbers[pos], tags[pos]
    suffix, canonical_suffix, bad_suffix, tail, wrong_tail, prose, detail = _dialect(pos, number="major")
    base_valid = f"v{number}.2.3-{tag.lower()}"
    base_canonical = f"v{number}.2.3-{tag.upper()}"
    valid, canonical, invalid = base_valid + suffix, base_canonical + canonical_suffix, base_canonical + bad_suffix
    template = r'''
std::size_t p=0;if(p>=input.size()||lower(input[p++])!='v')return fail(p,"version prefix");std::string major;
while(p<input.size()&&ascii_digit(input[p]))major.push_back(input[p++]);if(major.empty())return fail(p,"major");if(p>=input.size()||input[p++]!='.')return fail(p,"dot one");std::string minor;
while(p<input.size()&&ascii_digit(input[p]))minor.push_back(input[p++]);if(minor.empty())return fail(p,"minor");if(p>=input.size()||input[p++]!='.')return fail(p,"dot two");std::string patch;
while(p<input.size()&&ascii_digit(input[p]))patch.push_back(input[p++]);if(patch.empty())return fail(p,"patch");if(p>=input.size()||input[p]!='-')return fail(p,"label separator");++p;std::string label;
while(p<input.size()&&ascii_alnum(input[p]))label.push_back(upper(input[p++]));if(label.empty())return fail(p,"label");
@TAIL@
return pass("v"+major+"."+minor+"."+patch+"-"+label@RENDER@,p);
'''
    body = template.replace("@TAIL@", tail).replace("@RENDER@", _tail_render(pos))
    neg = template.replace("@TAIL@", wrong_tail).replace("@RENDER@", _tail_render(pos))
    return _wrap(body, neg, band=4, pos=pos,
                 contract=f"Parse `v<major>.<minor>.<patch>-<label>`, normalize the prefix and label case, then parse {prose}.",
                 valid=valid, canonical=canonical, invalid=invalid,
                 other=("", base_canonical, canonical + ".4", "v1..3-X"),
                 detail_assertion=f"a.version_component_count==3U&&({detail})")


def _path(task_id: str, pos: int, prefix: str) -> Contract:
    numbers = ("34", "14", "147", "123", "42", "26", "24", "68", "57", "84")
    tags = ("X9", "OK", "AZ", "ABC", "Q7", "A1", "R8", "A2", "ZX", "K4")
    number, tag = numbers[pos], tags[pos]
    suffix, canonical_suffix, bad_suffix, tail, wrong_tail, prose, detail = _dialect(pos, number="number")
    base_valid = f"<{prefix.lower()}/{number}/tmp/../{tag.lower()}>"
    base_canonical = f"<{prefix}/{number}/{tag}>"
    valid, canonical, invalid = base_valid + suffix, base_canonical + canonical_suffix, base_canonical + bad_suffix
    template = r'''
std::size_t p=0;if(p>=input.size()||input[p++]!='<')return fail(p,"path open");std::vector<std::string> segments;std::string current;
while(p<input.size()&&input[p]!='>'){char c=input[p++];if(c=='/'){if(current.empty())return fail(p-1U,"empty segment");if(current==".."){if(segments.empty())return fail(p-1U,"root escape");segments.pop_back();}else if(current!=".")segments.push_back(current);current.clear();}else{if(!ascii_alnum(c)&&c!='.'&&c!='-')return fail(p-1U,"path byte");current.push_back(upper(c));}}
if(current.empty())return fail(p,"empty final segment");if(current==".."){if(segments.empty())return fail(p,"root escape");segments.pop_back();}else if(current!=".")segments.push_back(current);if(p>=input.size()||input[p]!='>')return fail(p,"path close");++p;if(segments.size()<3U)return fail(p,"path depth");
std::string number=segments[1];std::string tag=segments.back();
@TAIL@
std::string out="<";for(std::size_t i=0;i<segments.size();++i){if(i)out+='/';out+=segments[i];}out+='>';return pass(out@RENDER@,p);
'''
    body = template.replace("@TAIL@", tail).replace("@RENDER@", _tail_render(pos))
    neg = template.replace("@TAIL@", wrong_tail).replace("@RENDER@", _tail_render(pos))
    return _wrap(body, neg, band=5, pos=pos,
                 contract=f"Scan one angle-framed relative path, reject empty segments, resolve `.` and `..` without root escape, uppercase at least three surviving components, then parse {prose}.",
                 valid=valid, canonical=canonical, invalid=invalid,
                 other=("", base_canonical, canonical + "x", "<../" + tag + ">", f"<{prefix}/{number}/{tag}/>" + canonical_suffix),
                 detail_assertion=f"a.normalized_segment_count.size()==1U&&a.normalized_segment_count[0]==3U&&({detail})")


def _unit(task_id: str, pos: int, prefix: str) -> Contract:
    numbers = ("34", "14", "147", "123", "42", "26", "24", "68", "57", "84")
    tags = ("X9", "OK", "AZ", "ABC", "Q7", "A1", "R8", "A2", "ZX", "K4")
    number, tag = numbers[pos], tags[pos]
    suffix, canonical_suffix, bad_suffix, tail, wrong_tail, prose, detail = _dialect(pos, number="whole")
    base_valid = f"{number}.50[{tag.lower()}]"
    base_canonical = f"{number}.50[{tag.upper()}]"
    valid, canonical, invalid = base_valid + suffix, base_canonical + canonical_suffix, base_canonical + bad_suffix
    template = r'''
std::size_t p=0;std::string whole;while(p<input.size()&&ascii_digit(input[p]))whole.push_back(input[p++]);if(whole.empty())return fail(p,"amount");if(p>=input.size()||input[p++]!='.')return fail(p,"decimal point");std::string fraction;
while(p<input.size()&&ascii_digit(input[p]))fraction.push_back(input[p++]);if(fraction.size()!=2U)return fail(p,"precision");if(p>=input.size()||input[p]!='[')return fail(p,"unit open");++p;std::string unit;
while(p<input.size()&&input[p]!=']'){char c=upper(input[p++]);if(!ascii_alnum(c))return fail(p-1U,"unit byte");unit.push_back(c);}if(p>=input.size()||input[p]!=']')return fail(p,"unit close");++p;if(unit.empty())return fail(p,"unit");
@TAIL@
return pass(whole+"."+fraction+"["+unit+"]"@RENDER@,p);
'''
    body = template.replace("@TAIL@", tail).replace("@RENDER@", _tail_render(pos))
    neg = template.replace("@TAIL@", wrong_tail).replace("@RENDER@", _tail_render(pos))
    return _wrap(body, neg, band=6, pos=pos,
                 contract=f"Parse a two-decimal quantity followed by a nonempty bracketed ASCII-alphanumeric unit, uppercase the unit, then parse {prose}.",
                 valid=valid, canonical=canonical, invalid=invalid,
                 other=("", base_canonical, canonical + "!", number + "[" + tag + "]"),
                 detail_assertion=f"a.unit_symbol_count.first=={len(tag)}U&&a.unit_symbol_count.second==2U&&({detail})")


def _ranges(task_id: str, pos: int, prefix: str) -> Contract:
    numbers = ("34", "14", "147", "123", "42", "26", "24", "68", "57", "84")
    tags = ("X9", "OK", "AZ", "ABC", "Q7", "A1", "R8", "A2", "ZX", "K4")
    number, tag = numbers[pos], tags[pos]
    start = int(number)
    suffix, canonical_suffix, bad_suffix, tail, wrong_tail, prose, detail = _dialect(pos, number="number")
    base_valid = f"[{start}-{start+2},{start+4}];{tag.lower()}"
    base_canonical = f"[{start}-{start+2},{start+4}];{tag.upper()}"
    valid, canonical, invalid = base_valid + suffix, base_canonical + canonical_suffix, base_canonical + bad_suffix
    template = r'''
std::size_t p=0;if(p>=input.size()||input[p++]!='[')return fail(p,"list open");std::vector<std::pair<int,int>> ranges;std::string number;
while(p<input.size()&&input[p]!=']'){std::string first;while(p<input.size()&&ascii_digit(input[p]))first.push_back(input[p++]);if(first.empty())return fail(p,"range start");int a=to_int(first);int b=a;if(p<input.size()&&input[p]=='-'){++p;std::string second;while(p<input.size()&&ascii_digit(input[p]))second.push_back(input[p++]);if(second.empty())return fail(p,"range end");b=to_int(second);if(b<a)return fail(p,"descending range");}ranges.push_back({a,b});if(number.empty())number=first;if(p<input.size()&&input[p]==','){++p;if(p>=input.size()||input[p]==']')return fail(p,"range after comma");}else if(p<input.size()&&input[p]!=']')return fail(p,"range separator");}
if(ranges.empty())return fail(p,"empty range list");if(p>=input.size()||input[p]!=']')return fail(p,"list close");++p;if(p>=input.size()||input[p]!=';')return fail(p,"tag separator");++p;std::string tag;while(p<input.size()&&ascii_alnum(input[p]))tag.push_back(upper(input[p++]));if(tag.empty())return fail(p,"tag");
@TAIL@
std::string out="[";for(std::size_t i=0;i<ranges.size();++i){if(i)out+=',';out+=std::to_string(ranges[i].first);if(ranges[i].second!=ranges[i].first)out+="-"+std::to_string(ranges[i].second);}return pass(out+"];"+tag@RENDER@,p);
'''
    body = template.replace("@TAIL@", tail).replace("@RENDER@", _tail_render(pos))
    neg = template.replace("@TAIL@", wrong_tail).replace("@RENDER@", _tail_render(pos))
    return _wrap(body, neg, band=7, pos=pos,
                 contract=f"Parse a nonempty bracketed comma list of nonnegative integers or ascending inclusive ranges followed by a symbolic tag, render minimal endpoints, uppercase the tag, then parse {prose}.",
                 valid=valid, canonical=canonical, invalid=invalid,
                 other=("", base_canonical, canonical + ",9", "[];" + tag + canonical_suffix, "[3-1];" + tag + canonical_suffix, f"[{start}-{start+2},{start+4},];{tag}" + canonical_suffix),
                 detail_assertion=f"a.range_count.has_value()&&*a.range_count==2U&&({detail})")


def _record(task_id: str, pos: int, prefix: str) -> Contract:
    numbers = ("34", "14", "147", "123", "42", "26", "24", "68", "57", "84")
    tags = ("X9", "OK", "AZ", "ABC", "Q7", "A1", "R8", "A2", "ZX", "K4")
    number, tag = numbers[pos], tags[pos]
    suffix, canonical_suffix, bad_suffix, tail, wrong_tail, prose, detail = _dialect(pos, number="number")
    base_valid = f"{{n={number};tag={tag.lower()}}}"
    base_canonical = f"{{N={number};TAG={tag.upper()}}}"
    valid, canonical, invalid = base_valid + suffix, base_canonical + canonical_suffix, base_canonical + bad_suffix
    template = r'''
std::size_t p=0;if(p>=input.size()||input[p++]!='{')return fail(p,"record open");std::map<std::string,std::string> fields;
while(p<input.size()&&input[p]!='}'){std::string key;while(p<input.size()&&ascii_alpha(input[p]))key.push_back(upper(input[p++]));if(key.empty()||p>=input.size()||input[p++]!='=')return fail(p,"field");std::string value;while(p<input.size()&&input[p]!=';'&&input[p]!='}')value.push_back(upper(input[p++]));if(value.empty()||fields.count(key))return fail(p,"duplicate or empty field");fields[key]=value;if(p<input.size()&&input[p]==';')++p;}
if(p>=input.size()||input[p]!='}')return fail(p,"record close");++p;if(!fields.count("N")||!fields.count("TAG")||fields.size()!=2U)return fail(p,"field set");std::string number=fields["N"];std::string tag=fields["TAG"];
if(number.empty()||!all_digits(number))return fail(p,"decimal n");if(tag.empty()||!all_alnum(tag))return fail(p,"alphanumeric tag");
@TAIL@
return pass("{N="+number+";TAG="+tag+"}"@RENDER@,p);
'''
    body = template.replace("@TAIL@", tail).replace("@RENDER@", _tail_render(pos))
    neg = template.replace("@TAIL@", wrong_tail).replace("@RENDER@", _tail_render(pos))
    return _wrap(body, neg, band=8, pos=pos,
                 contract=f"Parse exactly unique `n=<nonempty decimal>` and `tag=<nonempty ASCII alphanumeric>` fields inside braces, canonicalize names/order/tag case, then parse {prose}. Duplicate, absent, and extra fields fail.",
                 valid=valid, canonical=canonical, invalid=invalid,
                 other=("", base_canonical, canonical + "x", "{n=1;n=2;tag=X}" + canonical_suffix, "{n=X;tag=A}" + canonical_suffix),
                 detail_assertion=f"a.record_field_count.size()==2U&&a.record_field_count.at(\"N\")==1U&&a.record_field_count.at(\"TAG\")==1U&&({detail})")


def _frame(task_id: str, pos: int, prefix: str) -> Contract:
    numbers = ("34", "14", "147", "123", "42", "26", "24", "68", "57", "84")
    tags = ("X9", "OK", "AZ", "ABC", "Q7", "A1", "R8", "A2", "ZX", "K4")
    number, tag = numbers[pos], tags[pos]
    payload = number + tag
    suffix, canonical_suffix, bad_suffix, tail, wrong_tail, prose, detail = _dialect(pos, number="number")
    base_valid = f"{len(payload)}:{payload.lower()},"
    base_canonical = f"{len(payload)}:{payload.upper()},"
    valid, canonical, invalid = base_valid + suffix, base_canonical + canonical_suffix, base_canonical + bad_suffix
    short_payload = ("7", "A", "1", "A", "A", "A", "2", "A", "7", "A")[pos]
    requires_primary = pos in {0, 6, 8}
    template = r'''
std::size_t p=0;std::string length_text;while(p<input.size()&&ascii_digit(input[p]))length_text.push_back(input[p++]);if(length_text.empty()||p>=input.size()||input[p++]!=':')return fail(p,"length prefix");int length=to_int(length_text);if(length<0||static_cast<std::size_t>(length)>input.size()-p)return fail(p,"payload length");std::string payload;
for(int i=0;i<length;++i){char c=input[p++];if(!ascii_alnum(c))return fail(p-1U,"payload byte");payload.push_back(upper(c));}if(payload.empty())return fail(p,"empty payload");if(p>=input.size()||input[p]!=',')return fail(p,"frame terminator");++p;std::string number;for(char c:payload){if(!ascii_digit(c))break;number.push_back(c);}@PRIMARY@
@TAIL@
return pass(std::to_string(payload.size())+":"+payload+","@RENDER@,p);
'''
    template = template.replace("@PRIMARY@", 'if(number.empty())return fail(p,"primary decimal field");' if requires_primary else "")
    body = template.replace("@TAIL@", tail).replace("@RENDER@", _tail_render(pos))
    neg = template.replace("@TAIL@", wrong_tail).replace("@RENDER@", _tail_render(pos))
    return _wrap(body, neg, band=9, pos=pos,
                 contract=f"Parse a decimal length-prefixed nonempty ASCII-alphanumeric payload terminated by comma, uppercase it, and enforce the exact byte count. The maximal leading decimal run is the primary decimal field and is required only when the selected suffix dialect refers to it; then parse {prose}.",
                 valid=valid, canonical=canonical, invalid=invalid,
                 other=("", base_canonical, canonical + "x", f"{len(payload)+1}:{payload}," + canonical_suffix),
                 detail_assertion=f"a.declared_payload_bytes=={len(payload)}LL&&({detail})",
                 valid_variants=((f"1:{short_payload.lower()}," + suffix, f"1:{short_payload}," + canonical_suffix),))


BUILDERS = (_fixed, _locator, _quoted, _numeric, _version, _path, _unit, _ranges, _record, _frame)


def build_contract(task_id: str, api_stem: str, index: int) -> Contract:
    band, pos = divmod(index, 10)
    words = task_id.removeprefix("lex-").split("-")
    prefix = "".join(word[0] for word in words)[:3].upper()
    return BUILDERS[band](task_id, pos, prefix)
