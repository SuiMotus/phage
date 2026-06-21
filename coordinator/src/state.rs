use crate::{CoordinatorState, Node, Task, TaskStatus};
use chrono::Utc;
use uuid::Uuid;

impl CoordinatorState {
    pub fn register_node(
        &self,
        hostname: String,
        gpu_model: String,
        vram_bytes: u64,
        driver_version: String,
    ) -> String {
        let node_id = format!("ph_n_{}", &Uuid::new_v4().to_string()[..8]);

        let node = Node {
            node_id: node_id.clone(),
            hostname,
            gpu_model,
            vram_bytes,
            driver_version,
            model_loaded: None,
            last_heartbeat: Utc::now().timestamp(),
            gpu_utilization: 0.0,
            gpu_temp: 0,
            tasks_completed: 0,
        };

        self.nodes.insert(node_id.clone(), node);
        node_id
    }

    pub fn heartbeat(
        &self,
        node_id: &str,
        gpu_util: f32,
        vram_used: u64,
        temp: u32,
        model_loaded: Option<String>,
    ) -> bool {
        if let Some(mut node) = self.nodes.get_mut(node_id) {
            node.last_heartbeat = Utc::now().timestamp();
            node.gpu_utilization = gpu_util;
            node.gpu_temp = temp;
            node.model_loaded = model_loaded;
            true
        } else {
            false
        }
    }

    pub fn dead_nodes(&self, threshold_sec: i64) -> Vec<String> {
        let cutoff = Utc::now().timestamp() - threshold_sec;
        self.nodes
            .iter()
            .filter(|n| n.last_heartbeat < cutoff)
            .map(|n| n.node_id.clone())
            .collect()
    }

    pub fn submit_task(
        &self,
        prompt: String,
        verifier_cmd: String,
        model: String,
        temperature: f32,
        max_tokens: u32,
        best_of_n: u32,
    ) -> String {
        let task_id = format!("tsk_{}", &Uuid::new_v4().to_string()[..10]);

        let task = Task {
            task_id: task_id.clone(),
            prompt,
            verifier_cmd,
            model,
            temperature,
            max_tokens,
            best_of_n,
            status: TaskStatus::Queued,
            attempts: Vec::new(),
            created_at: Utc::now().timestamp(),
        };

        self.tasks.insert(task_id.clone(), task);
        task_id
    }

    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    pub fn active_tasks(&self) -> usize {
        self.tasks
            .iter()
            .filter(|t| matches!(t.status, TaskStatus::Queued | TaskStatus::Dispatched))
            .count()
    }
}
