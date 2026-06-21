use crate::{CoordinatorState, TaskStatus};

/// model VRAM requirements in bytes
fn model_vram_requirement(model: &str) -> u64 {
    match model {
        m if m.contains("7B") => 14 * 1024 * 1024 * 1024,
        m if m.contains("Lite") => 32 * 1024 * 1024 * 1024,
        m if m.contains("72B") => 40 * 1024 * 1024 * 1024,
        _ => 16 * 1024 * 1024 * 1024,
    }
}

impl CoordinatorState {
    /// find the best node for a task.
    /// prefers nodes that already have the model loaded (sticky routing).
    /// falls back to nodes with enough VRAM.
    pub fn pick_node(&self, model: &str) -> Option<String> {
        let vram_needed = model_vram_requirement(model);

        // first pass: nodes already running this model
        let sticky = self
            .nodes
            .iter()
            .filter(|n| {
                n.model_loaded.as_deref() == Some(model) && n.gpu_utilization < 90.0
            })
            .min_by(|a, b| {
                a.gpu_utilization
                    .partial_cmp(&b.gpu_utilization)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .map(|n| n.node_id.clone());

        if sticky.is_some() {
            return sticky;
        }

        // second pass: any node with enough VRAM
        self.nodes
            .iter()
            .filter(|n| n.vram_bytes >= vram_needed && n.gpu_utilization < 50.0)
            .min_by_key(|n| n.tasks_completed)
            .map(|n| n.node_id.clone())
    }

    /// dispatch queued tasks to available nodes.
    /// called periodically by the coordinator loop.
    pub async fn dispatch_round(&self) {
        let queue = self.task_queue.lock().await;
        let task_ids: Vec<String> = queue.clone();
        drop(queue);

        for task_id in task_ids {
            if let Some(mut task) = self.tasks.get_mut(&task_id) {
                if !matches!(task.status, TaskStatus::Queued) {
                    continue;
                }

                let dispatched = task.attempts.len() as u32;
                let remaining = task.best_of_n.saturating_sub(dispatched);

                for _ in 0..remaining {
                    if let Some(node_id) = self.pick_node(&task.model) {
                        task.attempts.push(crate::Attempt {
                            node_id,
                            passed: None,
                            output: None,
                            tokens: 0,
                            wall_ms: 0,
                            attestation: None,
                        });
                    }
                }

                if !task.attempts.is_empty() {
                    task.status = TaskStatus::Dispatched;
                }
            }
        }
    }
}
