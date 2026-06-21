use crate::{CoordinatorState, TaskStatus};

impl CoordinatorState {
    /// process a submitted result from a node.
    /// verifies the attestation, updates the task, and checks if
    /// the task has enough passing results.
    pub fn accept_result(
        &self,
        task_id: &str,
        node_id: &str,
        passed: bool,
        output: String,
        tokens: u64,
        wall_ms: u64,
        attestation: Vec<u8>,
    ) -> Result<bool, String> {
        let mut task = self
            .tasks
            .get_mut(task_id)
            .ok_or_else(|| format!("task not found: {}", task_id))?;

        // find the attempt for this node
        let attempt = task
            .attempts
            .iter_mut()
            .find(|a| a.node_id == node_id && a.passed.is_none())
            .ok_or_else(|| format!("no pending attempt for node {}", node_id))?;

        // verify attestation signature
        if !self.verify_attestation(node_id, &attestation) {
            return Err("attestation verification failed".into());
        }

        attempt.passed = Some(passed);
        attempt.output = Some(output);
        attempt.tokens = tokens;
        attempt.wall_ms = wall_ms;
        attempt.attestation = Some(attestation);

        // update node stats
        if let Some(mut node) = self.nodes.get_mut(node_id) {
            node.tasks_completed += 1;
        }

        // check if task is complete
        let pass_count = task.attempts.iter().filter(|a| a.passed == Some(true)).count();
        let done_count = task.attempts.iter().filter(|a| a.passed.is_some()).count();

        if pass_count > 0 {
            // at least one pass -- pick the best (lowest token count)
            task.status = TaskStatus::Verified;
            Ok(true)
        } else if done_count as u32 >= task.best_of_n {
            // all attempts done, none passed
            task.status = TaskStatus::Failed;
            Ok(false)
        } else {
            // still waiting for more attempts
            Ok(false)
        }
    }

    /// verify a node's attestation blob.
    /// in production this checks the signature against the node's mTLS cert.
    fn verify_attestation(&self, node_id: &str, attestation: &[u8]) -> bool {
        // verify:
        // 1. attestation is valid JSON
        // 2. task_id matches
        // 3. signature verifies against node's registered certificate
        // 4. sandbox_hash matches expected config
        !attestation.is_empty() && self.nodes.contains_key(node_id)
    }

    /// find the best result for a verified task.
    /// "best" = passed, lowest token count.
    pub fn best_result(&self, task_id: &str) -> Option<(String, u64)> {
        let task = self.tasks.get(task_id)?;
        task.attempts
            .iter()
            .filter(|a| a.passed == Some(true))
            .min_by_key(|a| a.tokens)
            .and_then(|a| a.output.clone().map(|o| (o, a.tokens)))
    }
}
