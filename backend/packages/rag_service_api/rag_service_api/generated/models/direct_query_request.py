from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="DirectQueryRequest")


@_attrs_define
class DirectQueryRequest:
    """
    Attributes:
        documents_text (str):
        query (str):
        llm_model (str | Unset):  Default: 'mistral:latest'.
        embedder_model (str | Unset):  Default: 'sentence-transformers/all-MiniLM-L6-v2'.
        top_k (int | Unset):  Default: 4.
        context_length (int | Unset):  Default: 8192.
        prompt_name (str | Unset):  Default: 'rag_short'.
    """

    documents_text: str
    query: str
    llm_model: str | Unset = "mistral:latest"
    embedder_model: str | Unset = "sentence-transformers/all-MiniLM-L6-v2"
    top_k: int | Unset = 4
    context_length: int | Unset = 8192
    prompt_name: str | Unset = "rag_short"
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        documents_text = self.documents_text

        query = self.query

        llm_model = self.llm_model

        embedder_model = self.embedder_model

        top_k = self.top_k

        context_length = self.context_length

        prompt_name = self.prompt_name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "documents_text": documents_text,
                "query": query,
            }
        )
        if llm_model is not UNSET:
            field_dict["llm_model"] = llm_model
        if embedder_model is not UNSET:
            field_dict["embedder_model"] = embedder_model
        if top_k is not UNSET:
            field_dict["top_k"] = top_k
        if context_length is not UNSET:
            field_dict["context_length"] = context_length
        if prompt_name is not UNSET:
            field_dict["prompt_name"] = prompt_name

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        documents_text = d.pop("documents_text")

        query = d.pop("query")

        llm_model = d.pop("llm_model", UNSET)

        embedder_model = d.pop("embedder_model", UNSET)

        top_k = d.pop("top_k", UNSET)

        context_length = d.pop("context_length", UNSET)

        prompt_name = d.pop("prompt_name", UNSET)

        direct_query_request = cls(
            documents_text=documents_text,
            query=query,
            llm_model=llm_model,
            embedder_model=embedder_model,
            top_k=top_k,
            context_length=context_length,
            prompt_name=prompt_name,
        )

        direct_query_request.additional_properties = d
        return direct_query_request

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
