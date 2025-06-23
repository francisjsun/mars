from mars import make

proj = make.Project(
    "test", target=make.Target(type="static_lib", source=["main.cpp"])
)

proj.add_target(
    make.Target(
        name="test2",
        type="exe",
        source=["main.cpp"],
        dependency_target_name=["test1", "test"],
    )
)

proj.add_target(
    make.Target(name="test1", type="static_lib", source=["main.cpp"])
)

proj.generate_cmake()
