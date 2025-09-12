/**
 * Simplified Workflow Status Schema
 * Matches the schema defined in workflow-status-tracking.md
 */

export interface WorkflowStatus {
  workflowInfo: {
    sessionId: string;
    appUrl: string;
    workflowType: "complete";
    startedAt: string; // ISO timestamp
    updatedAt: string; // ISO timestamp
    currentPhase: WorkflowPhase;
    overallStatus: "InProgress" | "Completed" | "Failed";
  };
  testPlan: {
    testSuites: TestSuite[];
  };
}

export interface TestSuite {
  suiteName: string;
  testFilePath: string; // Relative path to the test file
  testCases: TestCase[];
}

export interface TestCase {
  testCaseName: string;
  status: TestCaseStatus;
}

export type WorkflowPhase = "PlanGeneration" | "CodeGeneration" | "RunningAndFixing" | "Completed";

export type TestCaseStatus = 
  | "Generating" | "Generated"           // PlanGeneration & CodeGeneration phases
  | "Running" | "Errors Found" | "Fixing" | "Fixed"  // RunningAndFixing phase
  | "Pass" | "Fail";                     // Completed phase

// Phase-specific status constraints
export type TestCaseStatusForPhase<T extends WorkflowPhase> = 
  T extends "PlanGeneration" ? "Generating" | "Generated" :
  T extends "CodeGeneration" ? "Generating" | "Generated" :
  T extends "RunningAndFixing" ? "Running" | "Errors Found" | "Fixing" | "Fixed" :
  T extends "Completed" ? "Pass" | "Fail" :
  never;
