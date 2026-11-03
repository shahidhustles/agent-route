"""Google's IFEval instruction checkers (Apache 2.0), vendored from
google-research/instruction_following_eval. Only the imports changed."""
from . import instructions_registry


def follows_all(response, instruction_ids, kwargs_list, prompt):
    """Strict IFEval check: every instruction in the prompt must hold."""
    results = []
    for instruction_id, kwargs in zip(instruction_ids, kwargs_list):
        checker = instructions_registry.INSTRUCTION_DICT[instruction_id](instruction_id)
        checker.build_description(**{k: v for k, v in (kwargs or {}).items() if v is not None})
        args = checker.get_instruction_args()
        if args and 'prompt' in args:
            checker.build_description(prompt=prompt)
        results.append(bool(response and response.strip() and checker.check_following(response)))
    return all(results), results
