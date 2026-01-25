from mars import make as mmk

proj = mmk.Project(
    "test",
    target=mmk.Target(type=mmk.Target.Type.STATIC_LIB, source=["main.cpp"]),
)

proj.add_target(
    mmk.Target(
        name="test2",
        type=mmk.Target.Type.EXE,
        source="main.cpp",
        dependency_target=["test1", "test"],
    )
)

t_test1 = proj.add_target(
    mmk.Target(
        name="test1", type=mmk.Target.Type.STATIC_LIB, source=["main.cpp"]
    )
)

proj.add_sub_dir("sub_dir")

proj.generate()
