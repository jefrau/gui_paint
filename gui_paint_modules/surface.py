"""Surface — binds a Scene to an editor region and owns its registration.

The lifecycle (register the draw callback, enable, disable without leaving anything
behind) lands in task M1.5. For now this module only pins the class and its
documented constructor.
"""


class Surface:
    """Binds a Scene to an editor region and manages its lifecycle.

    Creating a Surface does nothing. ``enable()`` registers drawing, and later
    input, for the chosen region; ``disable()`` removes everything again.
    """

    def __init__(self, space_type, region_type="WINDOW", interactive=False):
        self.space_type = space_type
        self.region_type = region_type
        self.interactive = interactive
        self._handle = None
        self._router = None
        self._area_ptr = None
