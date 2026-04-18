from app.domain_profiles.legal import LegalDomainProfile
from app.modules.rag.text_utils import tajik_query_to_russian_hint


class TaxDomainProfile(LegalDomainProfile):
    def __init__(self) -> None:
        super().__init__()
        object.__setattr__(self, "name", "tax")
        object.__setattr__(self, "assistant_name", "SafeDocsAI")

    def greeting(self, language: str) -> str:
        if language == "tj":
            return (
                "Салом! Ман SafeDocsAI, ёрдамчии шумо оид ба андоз. Ба ман савол диҳед."
            )
        return "Здравствуйте! Я SafeDocsAI, ваш налоговый помощник. Задавайте вопросы."

    def prompt_injection_message(self, language: str) -> str:
        if language == "tj":
            return "Дархост рад шуд: савол дорои дастурҳои хатарнок аст. Лутфан саволи худро танҳо дар бораи мавзӯи андоз нависед."
        return "Запрос отклонен: обнаружена попытка обойти системные правила. Сформулируйте вопрос только по налоговой теме."

    def search_queries(self, query_text: str, language: str) -> list[str]:
        queries = [query_text]
        if language == "tj":
            hinted = tajik_query_to_russian_hint(query_text)
            if hinted and hinted != query_text:
                queries.append(hinted)
        return queries

    def answer_rules(self, language: str) -> str:
        return (
            "Answer as a tax-focused assistant using only the provided context. "
            "You may simplify the explanation style if requested, but never invent tax rules or obligations."
        )
