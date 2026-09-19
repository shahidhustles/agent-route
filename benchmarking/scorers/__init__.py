"""Deterministic scorers. Category pass rates come only from these functions."""
import json
import re


def response_text(result):
    if isinstance(result, str):
        return result
    return result.get('content') or ''


def _normalize(text):
    text = re.sub(r'\*+|#+|`+', '', text)
    return re.sub(r'\s+', ' ', text.strip().rstrip('.!?,;:')).lower()


def _parse_json(text):
    text = text.strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    match = re.search(r'[\[{]', text)
    if not match:
        return None
    for opener, closer in (('{', '}'), ('[', ']')):
        if text[match.start()] == opener:
            depth = 0
            for i in range(match.start(), len(text)):
                if text[i] == opener:
                    depth += 1
                elif text[i] == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[match.start():i + 1])
                        except ValueError:
                            return None
    return None


def _score_exact(scoring, result):
    return _normalize(response_text(result)) == _normalize(scoring['value'])


def _score_contains(scoring, result):
    haystack = response_text(result)
    if scoring.get('case_insensitive'):
        haystack = haystack.lower()
        return all(value.lower() in haystack for value in scoring['values'])
    return all(value in haystack for value in scoring['values'])


def _score_json(scoring, result):
    return _parse_json(response_text(result)) == scoring['expected']


def _score_tool_call(scoring, result):
    calls = result.get('tool_calls') or []
    expected = scoring.get('name')
    if expected is None:
        return not calls
    if len(calls) != 1:
        return False
    call = calls[0]
    name = call.get('function', {}).get('name') or call.get('name')
    if name != expected:
        return False
    raw = call.get('function', {}).get('arguments') if 'function' in call else call.get('arguments')
    try:
        args = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except ValueError:
        return False
    return all(_normalize(str(args.get(key, ''))) == _normalize(str(value))
               for key, value in (scoring.get('args') or {}).items())


def _constraint_ok(constraint, text):
    kind = constraint['kind']
    value = constraint['value']
    words = text.split()
    lines = [line for line in text.strip().splitlines() if line.strip()]
    lowered = text.lower()
    if kind == 'word_count':
        return len(words) == value
    if kind == 'min_words':
        return len(words) >= value
    if kind == 'max_words':
        return len(words) <= value
    if kind == 'line_count':
        return len(lines) == value
    if kind == 'forbidden':
        return str(value).lower() not in lowered
    if kind == 'required':
        return str(value).lower() in lowered
    if kind == 'starts_with':
        return text.strip().lower().startswith(str(value).lower())
    if kind == 'min_chars':
        return len(text.strip()) >= value
    if kind == 'max_chars':
        return len(text.strip()) <= value
    raise ValueError(f'Unknown constraint kind: {kind}')


def _score_constraints(scoring, result):
    text = response_text(result)
    return all(_constraint_ok(c, text) for c in scoring['constraints'])


_CONSTRAINT_KINDS = {
    'word_count', 'min_words', 'max_words', 'line_count', 'forbidden',
    'required', 'starts_with', 'min_chars', 'max_chars',
}

_SCORERS = {
    'exact': _score_exact,
    'contains': _score_contains,
    'json': _score_json,
    'tool_call': _score_tool_call,
    'constraints': _score_constraints,
}


def _validate_scoring(scoring):
    if scoring.get('type') not in _SCORERS:
        raise ValueError(f"Unknown scoring type: {scoring.get('type')}")
    for constraint in scoring.get('constraints', []):
        if constraint['kind'] not in _CONSTRAINT_KINDS:
            raise ValueError(f"Unknown constraint kind: {constraint['kind']}")


def score_case(case, result):
    """Return {'passed': bool, 'detail': str} for one case result."""
    _validate_scoring(case['scoring'])
    scorer = _SCORERS[case['scoring']['type']]
    try:
        passed = bool(scorer(case['scoring'], result))
        detail = '' if passed else 'scorer returned false'
    except Exception as error:  # malformed model output must score 0, not crash the run
        passed, detail = False, f'{type(error).__name__}: {error}'
    return {'passed': passed, 'detail': detail}
