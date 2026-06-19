use std::sync::Arc;
use dashmap::DashMap;

#[tokio::main]
async fn main() {
    tracing_subscriber::init();
    let nodes: Arc<DashMap<String, String>> = Arc::new(DashMap::new());
    tracing::info!("phage coordinator starting, {} nodes", nodes.len());
    tokio::signal::ctrl_c().await.unwrap();
}
