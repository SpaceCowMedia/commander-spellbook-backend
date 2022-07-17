import pulp as lp


class LpProblem(lp.LpProblem):
    def sequentialSolve(self, objectives, absoluteTols=None, relativeTols=None, solver=None, debug=False):
        if not (solver):
            solver = self.solver
        if not (solver):
            solver = lp.LpSolverDefault
        if not (absoluteTols):
            absoluteTols = [0] * len(objectives)
        if not (relativeTols):
            relativeTols = [1] * len(objectives)
        # time it
        self.startClock()
        statuses = []
        for i, (obj, absol, rel) in enumerate(
            zip(objectives, absoluteTols, relativeTols)
        ):
            self.setObjective(obj)
            status = solver.actualSolve(self)
            statuses.append(status)
            if debug:
                self.writeLP("%sSequence.lp" % i)
            if self.sense == lp.const.LpMinimize:
                self += obj <= lp.value(obj) * rel + absol, "Sequence_Objective_%s" % i
            elif self.sense == lp.const.LpMaximize:
                self += obj >= lp.value(obj) * rel + absol, "Sequence_Objective_%s" % i
        self.stopClock()
        self.solver = solver
        return statuses
