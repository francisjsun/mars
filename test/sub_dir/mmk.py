from mars import make

proj = make.Project.get_project()

test1 = proj.get_target("test1")
test1.add_source("sub_dir.cpp")
