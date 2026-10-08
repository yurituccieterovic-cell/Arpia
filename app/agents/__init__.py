def criar_isa_twin(*args, **kwargs):
    from .isa_twin import criar_isa_twin as _f
    return _f(*args, **kwargs)

def criar_amanda_twin(*args, **kwargs):
    from .amanda_twin import criar_amanda_twin as _f
    return _f(*args, **kwargs)

def criar_arvore_twin(*args, **kwargs):
    from .arvore_twin import criar_arvore_twin as _f
    return _f(*args, **kwargs)

def rodar_crew_assembleia(*args, **kwargs):
    from .crew_tucci import rodar_crew_assembleia as _f
    return _f(*args, **kwargs)

__all__ = ["criar_isa_twin", "criar_amanda_twin", "criar_arvore_twin", "rodar_crew_assembleia"]
