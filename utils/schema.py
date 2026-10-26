"""Small standard-library validation engine for the hospital's input schemas."""

import math
from decimal import Decimal, InvalidOperation
from typing import Union, get_args, get_origin


class ValidationError(ValueError):
    def __init__(self, errors):
        self._errors = errors
        super().__init__("; ".join(f"{e['loc']}: {e['msg']}" for e in errors))

    def errors(self):
        return list(self._errors)


class Field:
    def __init__(self, default=..., **constraints):
        self.default = default
        self.constraints = constraints


def field_validator(*fields, mode="after"):
    def decorate(method):
        method.__func__._field_rule = (fields, mode)
        return method
    return decorate


def model_validator(mode="after"):
    def decorate(method):
        method._model_rule = True
        return method
    return decorate


def _convert(value, annotation):
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Union and type(None) in args:
        if value is None:
            return None
        return _convert(value, next(t for t in args if t is not type(None)))
    if origin is list:
        if not isinstance(value, (list, tuple)):
            raise ValueError("Expected a list")
        return [_convert(v, args[0]) for v in value]
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if isinstance(value, annotation):
            return value
        if not isinstance(value, dict):
            raise ValueError("Expected a record")
        return annotation(**value)
    if annotation is str:
        if not isinstance(value, str):
            raise ValueError("Expected text")
        return value.strip()
    if annotation in (int, float, Decimal):
        if isinstance(value, bool) or value is None:
            raise ValueError("Expected a number")
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("Number must be finite")
        if annotation is int and number != number.to_integral_value():
            raise ValueError("Expected a whole number")
        result = annotation(str(value)) if annotation is Decimal else annotation(number)
        if annotation is float and not math.isfinite(result):
            raise ValueError("Number must be finite")
        return result
    return value


class BaseModel:
    """Validate declared fields and the hospital's field/record rules."""

    def __init__(self, **data):
        errors = []
        rules = []
        record_rules = []
        for name, method in vars(type(self)).items():
            func = method.__func__ if isinstance(method, classmethod) else method
            if hasattr(func, "_field_rule"):
                fields, mode = func._field_rule
                rules.append((fields, mode, getattr(type(self), name)))
            if hasattr(func, "_model_rule"):
                record_rules.append(name)
        for name, annotation in type(self).__annotations__.items():
            spec = getattr(type(self), name)
            value = data.get(name, spec.default)
            try:
                if value is ...:
                    raise ValueError("Field required")
                for fields, mode, rule in rules:
                    if name in fields and mode == "before":
                        value = rule(value)
                value = _convert(value, annotation)
                if value is not None:
                    for key, bound in spec.constraints.items():
                        if key == "min_length" and len(value) < bound:
                            raise ValueError(f"Must contain at least {bound} characters or items")
                        if key == "max_length" and len(value) > bound:
                            raise ValueError(f"Must contain at most {bound} characters or items")
                        if key in ("gt", "ge", "le", "lt"):
                            valid = {"gt": value > bound, "ge": value >= bound,
                                     "le": value <= bound, "lt": value < bound}[key]
                            if not valid:
                                raise ValueError(f"Value must satisfy {key} {bound}")
                for fields, mode, rule in rules:
                    if name in fields and mode == "after":
                        value = rule(value)
                setattr(self, name, value)
            except (ValueError, TypeError, InvalidOperation, OverflowError) as exc:
                errors.append({"loc": (name,), "msg": str(exc)})
        if errors:
            raise ValidationError(errors)
        for name in record_rules:
            try:
                getattr(self, name)()
            except ValueError as exc:
                errors.append({"loc": (), "msg": str(exc)})
        if errors:
            raise ValidationError(errors)

    def model_dump(self, exclude_none=False):
        def dump(value):
            if isinstance(value, BaseModel):
                return value.model_dump(exclude_none=exclude_none)
            if isinstance(value, list):
                return [dump(v) for v in value]
            return value
        return {k: dump(v) for k, v in vars(self).items()
                if not exclude_none or v is not None}
