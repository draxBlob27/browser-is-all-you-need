"""Artifact-derived semantic diversity screening for circular-deque tasks."""
from __future__ import annotations
import json,re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable,Sequence

NORMALIZER_VERSION="circular-deque-semantic-v4"
DUPLICATE_THRESHOLD=0.78
HOLDOUT_THRESHOLD=0.72
_CPP_PRESERVED={"alignof","and","auto","bool","break","case","catch","char","class","const","constexpr","continue","default","delete","do","double","else","enum","explicit","false","float","for","friend","if","inline","int","long","namespace","new","noexcept","not","nullptr","operator","or","private","protected","public","return","short","signed","sizeof","static","struct","switch","template","this","throw","true","try","typedef","typename","union","unsigned","using","virtual","void","volatile","while","size_t","string","vector","deque","optional","pair","unordered_set","unordered_map","array","numeric_limits","nullopt","min","max","minmax_element","from_chars","push_front","push_back","pop_front","pop_back","front","back","begin","end","insert","erase","clear","empty","size","count","find","sort","stable_sort","append","reset","move","make_pair"}
_DOC_STOP={"a","an","and","as","at","be","by","for","from","has","in","is","it","of","on","or","that","the","this","to","with","without","must","task","implement","local","candidate","material","dataset","release"}
_TOKEN_RE=re.compile(r"[A-Za-z_][A-Za-z_0-9]*|::|->|==|!=|<=|>=|&&|\|\||\+\+|--|<<|>>|[{}()\[\];,.?:%+\-*/<>=!&|^~]")

@dataclass(frozen=True)
class SemanticArtifact:
    task_id:str;docs:str;api:str;source:str;tests:str

@dataclass(frozen=True)
class PairwiseScore:
    left:str;right:str;api:float;source:float;tests:float;docs:float;combined:float
    def reason(self)->str:
        return f"{self.left}:{self.right}:combined={self.combined:.3f}:api={self.api:.3f}:source={self.source:.3f}:tests={self.tests:.3f}:docs={self.docs:.3f}"

def _without_cpp_noise(text:str)->str:
    text=re.sub(r"/\*.*?\*/"," ",text,flags=re.S)
    text=re.sub(r"//[^\n]*"," ",text)
    text=re.sub(r'"(?:\\.|[^"\\])*"'," LIT ",text)
    text=re.sub(r"'(?:\\.|[^'\\])*'"," LIT ",text)
    return re.sub(r"\b(?:0[xX][0-9A-Fa-f]+|\d+)(?:[uUlLfF]+)?\b"," NUM ",text)

def normalize_cpp(text:str)->tuple[str,...]:
    out=[]
    for token in _TOKEN_RE.findall(_without_cpp_noise(text)):
        if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*",token):
            low=token.lower()
            out.append(token if token in {"LIT","NUM"} else low if low in _CPP_PRESERVED else "ID")
        else:out.append(token)
    return tuple(out)

def normalize_docs(text:str)->tuple[str,...]:
    cleaned=re.sub(r"\x60[^\x60]*\x60"," API ",text.lower())
    cleaned=re.sub(r"\b\d+\b"," NUM ",cleaned)
    words=re.findall(r"[a-z_]+",cleaned)
    return tuple("ID" if word not in {"api","num"} else word for word in words if word not in _DOC_STOP)

def _ngrams(tokens:Sequence[str],width:int)->frozenset[tuple[str,...]]:
    if not tokens:return frozenset()
    if len(tokens)<width:return frozenset({tuple(tokens)})
    return frozenset(tuple(tokens[i:i+width]) for i in range(len(tokens)-width+1))

def _jaccard(a:frozenset,b:frozenset)->float:
    if not a and not b:return 1.0
    union=a|b
    return len(a&b)/len(union) if union else 1.0

def compare(a:SemanticArtifact,b:SemanticArtifact)->PairwiseScore:
    api=_jaccard(_ngrams(normalize_cpp(a.api),4),_ngrams(normalize_cpp(b.api),4))
    source=_jaccard(_ngrams(normalize_cpp(a.source),5),_ngrams(normalize_cpp(b.source),5))
    tests=_jaccard(_ngrams(normalize_cpp(a.tests),5),_ngrams(normalize_cpp(b.tests),5))
    docs=_jaccard(_ngrams(normalize_docs(a.docs),3),_ngrams(normalize_docs(b.docs),3))
    return PairwiseScore(a.task_id,b.task_id,api,source,tests,docs,.20*api+.45*source+.25*tests+.10*docs)

def pairwise_scores(items:Sequence[SemanticArtifact])->tuple[PairwiseScore,...]:
    return tuple(compare(items[i],items[j]) for i in range(len(items)) for j in range(i+1,len(items)))

def _is_duplicate(score:PairwiseScore,threshold:float)->bool:
    return score.combined>=threshold or score.source>=.90 or (score.source>=.82 and score.tests>=.68) or (score.api>=.90 and score.source>=.76)

def assert_semantic_diversity(items:Sequence[SemanticArtifact],*,threshold:float=DUPLICATE_THRESHOLD)->tuple[PairwiseScore,...]:
    ids=[x.task_id for x in items]
    if len(ids)!=len(set(ids)):raise RuntimeError("duplicate_family:duplicate_task_id")
    scores=pairwise_scores(items);bad=[x for x in scores if _is_duplicate(x,threshold)]
    if bad:raise RuntimeError("duplicate_family:"+max(bad,key=lambda x:x.combined).reason())
    return scores

def assert_no_holdout_overlap(candidates:Sequence[SemanticArtifact],holdouts:Sequence[SemanticArtifact],*,threshold:float=HOLDOUT_THRESHOLD)->tuple[PairwiseScore,...]:
    scores=tuple(compare(a,b) for a in candidates for b in holdouts);bad=[x for x in scores if _is_duplicate(x,threshold)]
    if bad:raise RuntimeError("benchmark_content_overlap:"+max(bad,key=lambda x:x.combined).reason())
    return scores

def load_artifact(root:Path)->SemanticArtifact:
    docs="\n".join(p.read_text() for p in sorted((root/".docs").glob("*.md")))
    config=json.loads((root/".meta/config.json").read_text())
    examples=config["files"]["example"]
    api=(root/examples[0]).read_text()
    source="\n".join((root/x).read_text() for x in examples)
    paths=[root/x for x in config["files"]["test"]]+sorted((root/".meta").glob("*test*.cpp"))
    tests="\n".join(p.read_text() for p in paths)
    return SemanticArtifact(root.name,docs,api,source,tests)

def load_holdout(root:Path)->SemanticArtifact:
    docs="\n".join(p.read_text() for p in sorted((root/".docs").glob("*.md")))
    api="\n".join(p.read_text() for p in sorted((root/".meta").glob("example.*")))
    source=api+"\n"+"\n".join(p.read_text() for p in sorted(root.glob("*.cpp")))
    tests="\n".join(p.read_text() for p in sorted(root.glob("*test*.cpp")))
    return SemanticArtifact(root.name,docs,api,source,tests)

def strongest(scores:Iterable[PairwiseScore])->PairwiseScore|None:
    values=tuple(scores)
    return max(values,key=lambda x:x.combined) if values else None
