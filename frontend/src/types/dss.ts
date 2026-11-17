
export type DSSRunStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED'

export type DSSModuleCode =
  | 'F1'
  | 'F2'
  | 'F3'
  | 'F4'
  | 'F5'

export type DSSOptionMode = 'DIRECT' | 'HUB'

export type DSSOptionStatus =
  | 'FEASIBLE'
  | 'BLOCKED'
  | 'EXCLUDED'

export type DSSScenarioType =
  | 'NORMAL'
  | 'INSUFFICIENT_VEHICLES'
  | 'TIME_CONFLICT'

export type DSSModuleStatus =
  | 'COMPLETED'
  | 'BLOCKED'
  | 'SKIPPED'

export interface DSSReason {
  code: string
  module: DSSModuleCode
  message: string
}

export interface DSSScenario {
  id: string
  name: string
  description: string
  scenario_type: DSSScenarioType
  service_date: string
  demand_count: number
  created_at: string
  is_demo: boolean
}

export interface DSSModuleResult {
  module: DSSModuleCode
  title: string
  status: DSSModuleStatus
  summary: string
  details: string[]
}

export interface DSSRouteStop {
  sequence: number
  location_name: string
  stop_type: 'PICKUP' | 'HUB' | 'DELIVERY'
  arrival_time: string
  departure_time: string
}

export interface DSSCandidate {
  id: string
  demand_ids: string[]
  supplier_names: string[]
  total_quantity_kg: number
  status: 'ELIGIBLE' | 'EXCLUDED'
  reasons: DSSReason[]
}

export interface DSSOption {
  id: string
  name: string
  mode: DSSOptionMode
  status: DSSOptionStatus

  demand_ids: string[]
  vehicle_name: string
  vehicle_count: number
  capacity_kg: number
  total_quantity_kg: number

  estimated_cost_vnd: number | null
  estimated_distance_km: number | null

  stops: DSSRouteStop[]
  reasons: DSSReason[]
}

export interface DSSSnapshot {
  captured_at: string
  source: 'DEMO_FIXTURE'
  scenario_id: string
  input: {
    service_date: string
    demand_count: number
    scenario_type: DSSScenarioType
    note: string
  }
  output: {
    candidate_count: number
    option_count: number
    feasible_count: number
    blocked_count: number
  }
}

export interface DSSRun {
  id: string
  scenario_id: string
  scenario_name: string
  status: DSSRunStatus
  started_at: string
  completed_at: string | null

  is_demo: boolean
  simulation_version: string

  modules: DSSModuleResult[]
  candidates: DSSCandidate[]
  options: DSSOption[]
  snapshot: DSSSnapshot
}

export interface DSSCreateScenarioInput {
  name: string
  description: string
  service_date: string
  demand_count: number
  scenario_type: DSSScenarioType
}

export interface DSSService {
  listScenarios(): Promise<DSSScenario[]>

  getScenario(
    scenarioId: string
  ): Promise<DSSScenario | null>

  createScenario(
    input: DSSCreateScenarioInput
  ): Promise<DSSScenario>

  listRuns(
    scenarioId?: string
  ): Promise<DSSRun[]>

  getRun(
    runId: string
  ): Promise<DSSRun | null>

  runScenario(
    scenarioId: string
  ): Promise<DSSRun>

  getOption(
    runId: string,
    optionId: string
  ): Promise<DSSOption | null>
}