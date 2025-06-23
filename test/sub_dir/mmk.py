from mars import make

proj = make.Project.get_project()

test1 = proj.get_target("test1")
if test1 is not None:
    test1.add_source("sub_dir.cpp")
