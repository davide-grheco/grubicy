import signac


def main():
    project = signac.init_project()

    experiments = [
        (1, 10, 0.1),
        (1, 10, 0.2),
        (1, 20, 0.1),
        (1, 20, 0.2),
        (2, 10, 0.1),
    ]

    for p1, p2, p3 in experiments:
        s1_sp = {"subproject": "s1", "p1": p1}
        project.open_job(s1_sp).init()

        s2_sp = {"subproject": "s2", "parent_s1": s1_sp, "p2": p2}
        project.open_job(s2_sp).init()

        s3_sp = {"subproject": "s3", "parent_s2": s2_sp, "p3": p3}
        project.open_job(s3_sp).init()

    s1 = list(project.find_jobs({"subproject": "s1"}))
    s2 = list(project.find_jobs({"subproject": "s2"}))
    s3 = list(project.find_jobs({"subproject": "s3"}))
    print("jobs created:")
    print("  s1:", len(s1), "(unique p1)")
    print("  s2:", len(s2), "(unique (p1,p2))")
    print("  s3:", len(s3), "(unique (p1,p2,p3))")


if __name__ == "__main__":
    main()
