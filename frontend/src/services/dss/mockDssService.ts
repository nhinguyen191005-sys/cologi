
import type {
  DSSCreateScenarioInput,
  DSSOption,
  DSSRun,
  DSSScenario,
  DSSService,
} from '../../types/dss'

import { demoScenarios } from '../../mocks/dss/scenarios'
import { buildMockRun } from '../../mocks/dss/mockResults'

/* =========================================
   IN-MEMORY MOCK DATABASE
========================================= */

let scenarios: DSSScenario[] = demoScenarios.map(
  (item) => ({ ...item })
)

let runs: DSSRun[] = []

let scenarioCounter = 4
let runCounter = 1

/* =========================================
   UTILS
========================================= */

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function nextScenarioId(): string {
  const id = `SCN-${String(scenarioCounter).padStart(3, '0')}`
  scenarioCounter += 1
  return id
}

function nextRunId(): string {
  const id = `RUN-${String(runCounter).padStart(4, '0')}`
  runCounter += 1
  return id
}

function assertValidScenario(
  input: DSSCreateScenarioInput
) {
  if (!input.name.trim()) {
    throw new Error('Vui lòng nhập tên kịch bản.')
  }

  if (!/^\d{4}-\d{2}-\d{2}$/.test(input.service_date)) {
    throw new Error('Ngày vận chuyển không hợp lệ.')
  }

  if (
    !Number.isInteger(input.demand_count) ||
    input.demand_count < 1
  ) {
    throw new Error(
      'Số nhu cầu phải là số nguyên lớn hơn 0.'
    )
  }
}

/* =========================================
   SERVICE IMPLEMENTATION
========================================= */

export const mockDssService: DSSService = {
  async listScenarios(): Promise<DSSScenario[]> {
    return clone(
      [...scenarios].sort((a, b) =>
        b.created_at.localeCompare(a.created_at)
      )
    )
  },

  async getScenario(
    scenarioId: string
  ): Promise<DSSScenario | null> {
    const scenario = scenarios.find(
      (item) => item.id === scenarioId
    )

    return scenario ? clone(scenario) : null
  },

  async createScenario(
    input: DSSCreateScenarioInput
  ): Promise<DSSScenario> {
    assertValidScenario(input)

    const scenario: DSSScenario = {
      id: nextScenarioId(),
      name: input.name.trim(),
      description: input.description.trim(),
      scenario_type: input.scenario_type,
      service_date: input.service_date,
      demand_count: input.demand_count,
      created_at: new Date().toISOString(),
      is_demo: true,
    }

    scenarios = [scenario, ...scenarios]

    return clone(scenario)
  },

  async listRuns(
    scenarioId?: string
  ): Promise<DSSRun[]> {
    const selected = scenarioId
      ? runs.filter(
          (item) => item.scenario_id === scenarioId
        )
      : runs

    return clone(
      [...selected].sort((a, b) =>
        b.started_at.localeCompare(a.started_at)
      )
    )
  },

  async getRun(
    runId: string
  ): Promise<DSSRun | null> {
    const run = runs.find(
      (item) => item.id === runId
    )

    return run ? clone(run) : null
  },

  async runScenario(
    scenarioId: string
  ): Promise<DSSRun> {
    const scenario = scenarios.find(
      (item) => item.id === scenarioId
    )

    if (!scenario) {
      throw new Error('Không tìm thấy kịch bản.')
    }

    const run = buildMockRun(
      scenario,
      nextRunId(),
      new Date().toISOString()
    )

    runs = [run, ...runs]

    return clone(run)
  },

  async getOption(
    runId: string,
    optionId: string
  ): Promise<DSSOption | null> {
    const run = runs.find(
      (item) => item.id === runId
    )

    const option = run?.options.find(
      (item) => item.id === optionId
    )

    return option ? clone(option) : null
  },
}