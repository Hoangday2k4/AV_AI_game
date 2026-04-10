class Scene:

    def __init__(self):

        self.objects = []

    def add(self, obj):

        self.objects.append(obj)

    def update(self, action):

        for obj in self.objects:

            if hasattr(obj, "update"):
                obj.update(action)

    def draw(self, screen):

        for obj in self.objects:

            if hasattr(obj, "draw"):
                obj.draw(screen)