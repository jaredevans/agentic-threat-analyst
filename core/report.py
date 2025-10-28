from tabulate import tabulate

def print_findings(findings):
    rows = []
    for r,severity,desc in findings[:200]:
        rows.append([severity.upper(), r, desc])
    print(tabulate(rows, headers=["SEV","RULE","DETAILS"], tablefmt="github"))
