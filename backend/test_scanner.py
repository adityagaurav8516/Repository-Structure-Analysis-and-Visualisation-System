import json

from app.scanner import scan_repo


if __name__ == "__main__":
    graph = scan_repo(r"C:/Users/adity/desktop/test_repo")

    print("nodes:", len(graph["nodes"]))
    print("edges:", len(graph["edges"]))
    print("dependency edges:", graph["stats"]["dependency_edges"])

    print("\ndependency edges:")
    for edge in graph["edges"]:
        if edge["type"] == "depends_on":
            print(f"{edge['source']} -> {edge['target']}")

    with open("graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)