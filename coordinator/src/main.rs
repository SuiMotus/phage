use std::sync::Arc;
use dashmap::DashMap;
use uuid::Uuid;
use chrono::Utc;
use serde::{Deserialize, Serialize};

mod state;
mod dispatch;
mod verify;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Node {
    pub node_id: String,
    pub hostname: String,
    pub gpu_model: String,
    pub vram_bytes: u64,
    pub driver_version: String,
    pub model_loaded: Option<String>,
    pub last_heartbeat: i64,
    pub gpu_utilization: f32,
    pub gpu_temp: u32,
    pub tasks_completed: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub task_id: String,
    pub prompt: String,
    pub verifier_cmd: String,
    pub model: String,
    pub temperature: f32,
    pub max_tokens: u32,
    pub best_of_n: u32,
    pub status: TaskStatus,
    pub attempts: Vec<Attempt>,
    pub created_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TaskStatus {
    Queued,
    Dispatched,
    Verified,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Attempt {
    pub node_id: String,
    pub passed: Option<bool>,
    pub output: Option<String>,
    pub tokens: u64,
    pub wall_ms: u64,
    pub attestation: Option<Vec<u8>>,
}

pub struct CoordinatorState {
    pub nodes: DashMap<String, Node>,
    pub tasks: DashMap<String, Task>,
    pub task_queue: tokio::sync::Mutex<Vec<String>>,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::init();

    let state = Arc::new(CoordinatorState {
        nodes: DashMap::new(),
        tasks: DashMap::new(),
        task_queue: tokio::sync::Mutex::new(Vec::new()),
    });

    tracing::info!(
        "phage coordinator v{} starting",
        env!("CARGO_PKG_VERSION")
    );
    tracing::info!("listening on 0.0.0.0:9090");

    // gRPC server would bind here
    // tonic::transport::Server::builder()
    //     .add_service(...)
    //     .serve(addr)
    //     .await
    //     .unwrap();

    // for now, wait for ctrl-c
    tokio::signal::ctrl_c().await.unwrap();
    tracing::info!("shutting down, {} nodes registered", state.nodes.len());
}
