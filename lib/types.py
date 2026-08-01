"""
Types matching seudoe/src/scraper/types.ts
Preserves the same structure for CachedProblem and Block-based statements
"""

from typing import Literal, Union, Optional, List
from dataclasses import dataclass, field, asdict


@dataclass
class ParagraphBlock:
    type: Literal['paragraph'] = 'paragraph'
    html: str = ''


@dataclass
class CodeBlock:
    type: Literal['code'] = 'code'
    code: str = ''
    language: Optional[str] = None


@dataclass
class ImageBlock:
    type: Literal['image'] = 'image'
    src: str = ''
    alt: Optional[str] = None


@dataclass
class TableBlock:
    type: Literal['table'] = 'table'
    html: str = ''


@dataclass
class ListBlock:
    type: Literal['list'] = 'list'
    ordered: bool = False
    items: List[str] = field(default_factory=list)


# Union type for all block types
Block = Union[ParagraphBlock, CodeBlock, ImageBlock, TableBlock, ListBlock]


@dataclass
class Example:
    input: str = ''
    output: str = ''
    explanation: Optional[str] = None

    def to_dict(self):
        d = {'input': self.input, 'output': self.output}
        if self.explanation:
            d['explanation'] = self.explanation
        return d


@dataclass
class ProblemStatement:
    title: str = ''
    timeLimit: str = ''
    memoryLimit: str = ''
    description: List[Block] = field(default_factory=list)
    input: List[Block] = field(default_factory=list)
    output: List[Block] = field(default_factory=list)
    examples: List[Example] = field(default_factory=list)
    note: Optional[List[Block]] = None

    def to_dict(self):
        d = {
            'title': self.title,
            'timeLimit': self.timeLimit,
            'memoryLimit': self.memoryLimit,
            'description': [asdict(b) for b in self.description],
            'input': [asdict(b) for b in self.input],
            'output': [asdict(b) for b in self.output],
            'examples': [e.to_dict() for e in self.examples]
        }
        if self.note:
            d['note'] = [asdict(b) for b in self.note]
        return d


@dataclass
class CachedProblem:
    contestId: int = 0
    index: str = ''
    cachedAt: int = 0  # unix timestamp seconds
    version: int = 1
    statement: Optional[ProblemStatement] = None

    def to_dict(self):
        return {
            'contestId': self.contestId,
            'index': self.index,
            'cachedAt': self.cachedAt,
            'version': self.version,
            'statement': self.statement.to_dict() if self.statement else None
        }
