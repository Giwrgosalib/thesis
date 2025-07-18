import torch
import torch.nn as nn
import torch.optim as optim

# --- 1. Model Architecture ---
# We will define the BiLSTM-CRF model here.
# For now, it's a placeholder.

class BiLSTM_CRF(nn.Module):
    def __init__(self, vocab_size, tag_to_ix, embedding_dim, hidden_dim):
        super(BiLSTM_CRF, self).__init__()
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim
        self.vocab_size = vocab_size
        self.tag_to_ix = tag_to_ix
        self.tagset_size = len(tag_to_ix)

        # --- Layers ---
        # Word embeddings
        self.word_embeds = nn.Embedding(vocab_size, embedding_dim)
        
        # LSTM layer
        self.lstm = nn.LSTM(embedding_dim, hidden_dim // 2,
                            num_layers=1, bidirectional=True)
                            
        # Linear layer that maps the output of the LSTM to tag space
        self.hidden2tag = nn.Linear(hidden_dim, self.tagset_size)

        print("Model Initialized!")
        # --- CRF Layer ---
        # Matrix of transition parameters. Entry i,j is the score of transitioning from i to j.
        self.transitions = nn.Parameter(
            torch.randn(self.tagset_size, self.tagset_size))

        # These two statements enforce the constraint that we never transfer
        # to the start tag and we never transfer from the stop tag
        self.transitions.data[tag_to_ix["START_TAG"], :] = -10000
        self.transitions.data[:, tag_to_ix["STOP_TAG"]] = -10000

        print("Model Initialized with CRF layer!")

    def _get_lstm_features(self, sentence):
        """Helper function to get the emissions score from the BiLSTM."""
        embeds = self.word_embeds(sentence).view(len(sentence), 1, -1)
        lstm_out, _ = self.lstm(embeds)
        lstm_out = lstm_out.view(len(sentence), self.hidden_dim)
        lstm_feats = self.hidden2tag(lstm_out)
        return lstm_feats

    def _forward_alg(self, feats):
        """Calculates the partition function for the CRF."""
        init_alphas = torch.full((1, self.tagset_size), -10000.)
        init_alphas[0][self.tag_to_ix["START_TAG"]] = 0.

        forward_var = init_alphas

        for feat in feats:
            alphas_t = []
            for next_tag in range(self.tagset_size):
                emit_score = feat[next_tag].view(1, -1).expand(1, self.tagset_size)
                trans_score = self.transitions[next_tag].view(1, -1)
                next_tag_var = forward_var + trans_score + emit_score
                alphas_t.append(torch.logsumexp(next_tag_var, dim=1).view(1))
            forward_var = torch.cat(alphas_t).view(1, -1)
        
        terminal_var = forward_var + self.transitions[self.tag_to_ix["STOP_TAG"]]
        alpha = torch.logsumexp(terminal_var, dim=1)
        return alpha

    def _score_sentence(self, feats, tags):
        """Calculates the score of a given sequence of tags."""
        score = torch.zeros(1)
        tags = torch.cat([torch.tensor([self.tag_to_ix["START_TAG"]], dtype=torch.long), tags])
        for i, feat in enumerate(feats):
            score = score + \
                self.transitions[tags[i + 1], tags[i]] + feat[tags[i + 1]]
        score = score + self.transitions[self.tag_to_ix["STOP_TAG"], tags[-1]]
        return score

    def neg_log_likelihood(self, sentence, tags):
        """This is the loss function for the CRF."""
        feats = self._get_lstm_features(sentence)
        forward_score = self._forward_alg(feats)
        gold_score = self._score_sentence(feats, tags)
        return forward_score - gold_score

    def _viterbi_decode(self, feats):
        backpointers = []

        # Initialize the viterbi variables in log space
        init_vvars = torch.full((1, self.tagset_size), -10000.)
        init_vvars[0][self.tag_to_ix["START_TAG"]] = 0

        # forward_var at step i holds the viterbi variables for step i-1
        forward_var = init_vvars
        for feat in feats:
            bptrs_t = []  # holds the backpointers for this step
            viterbivars_t = []  # holds the viterbi variables for this step

            for next_tag in range(self.tagset_size):
                next_tag_var = forward_var + self.transitions[next_tag]
                best_tag_id = torch.argmax(next_tag_var)
                bptrs_t.append(best_tag_id)
                viterbivars_t.append(next_tag_var[0][best_tag_id].view(1))
            forward_var = (torch.cat(viterbivars_t) + feat).view(1, -1)
            backpointers.append(bptrs_t)

        # Transition to STOP_TAG
        terminal_var = forward_var + self.transitions[self.tag_to_ix["STOP_TAG"]]
        best_tag_id = torch.argmax(terminal_var)
        path_score = terminal_var[0][best_tag_id]

        # Follow the back pointers to decode the best path.
        best_path = [best_tag_id]
        for bptrs_t in reversed(backpointers):
            best_tag_id = bptrs_t[best_tag_id]
            best_path.append(best_tag_id)
        # Pop off the start tag (we dont want to return that to the user)
        start = best_path.pop()
        assert start == self.tag_to_ix["START_TAG"]  # Sanity check
        best_path.reverse()
        return path_score, best_path

    def forward(self, sentence):  # dont confuse this with _forward_alg above.
        """
        This method, also known as the Viterbi algorithm, is used for inference
        to find the best path of tags for a given sentence.
        """
        # Get the emission scores from the BiLSTM
        lstm_feats = self._get_lstm_features(sentence)

        # Find the best path, given the features.
        score, tag_seq = self._viterbi_decode(lstm_feats)
        return score, tag_seq

# --- 2. Data Preparation ---
# We will add functions to process the training data here.

def prepare_sequence(seq, to_ix):
    # This function will convert a sequence of words to a sequence of indices.
    idxs = [to_ix[w] for w in seq]
    return torch.tensor(idxs, dtype=torch.long)

# --- 3. Training ---
# This is where the main training loop will go.

def train_model():
    # --- Mock Data (for demonstration) ---
    # In a real scenario, this would come from your dataset.csv
    training_data = [
        ("find me a new iPhone".split(), "O O O B-COND B-PROD".split()),
        ("show me used laptops under 500".split(), "O O B-COND B-PROD O O".split())
    ]

    # --- Vocabulary and Tag Mappings ---
    word_to_ix = {}
    for sentence, tags in training_data:
        for word in sentence:
            if word not in word_to_ix:
                word_to_ix[word] = len(word_to_ix)

    # We need a consistent tag set
    tag_to_ix = {
        "B-PROD": 0, "I-PROD": 1, "B-COND": 2, "I-COND": 3, "O": 4,
        # We will also need START and STOP tags for the CRF layer later
        "START_TAG": 5, "STOP_TAG": 6
    }

    # --- Model Initialization ---
    EMBEDDING_DIM = 128
    HIDDEN_DIM = 256
    
    model = BiLSTM_CRF(len(word_to_ix), tag_to_ix, EMBEDDING_DIM, HIDDEN_DIM)
    optimizer = optim.SGD(model.parameters(), lr=0.01, weight_decay=1e-4)

    print("Starting training...")
    
    # --- Training Loop ---
    for epoch in range(1, 3): # Run for a few epochs for demonstration
        print(f"--- Epoch {epoch} ---")
        for sentence, tags in training_data:
            # Step 1. Remember that Pytorch accumulates gradients.
            # We need to clear them out before each instance.
            model.zero_grad()

            # Step 2. Get our inputs in the right format, i.e. turn them into
            # Tensors of word indices.
            sentence_in = prepare_sequence(sentence, word_to_ix)
            targets = torch.tensor([tag_to_ix[t] for t in tags], dtype=torch.long)

            # Step 3. Run our forward pass.
            loss = model.neg_log_likelihood(sentence_in, targets)

            # Step 4. Compute the loss, gradients, and update the parameters by
            # calling optimizer.step()
            loss.backward()
            optimizer.step()
        print(f"Epoch {epoch} complete. Loss (placeholder): {loss.item()}")

    print("\nTraining loop is complete. The model has been updated.")

    # --- Inference ---
    # Check the predictions after training
    with torch.no_grad():
        precheck_sent = prepare_sequence(training_data[0][0], word_to_ix)
        print("\n--- Prediction Example ---")
        print("Sentence:", training_data[0][0])
        score, tag_sequence = model(precheck_sent)
        
        # Convert tag indices back to tags
        ix_to_tag = {v: k for k, v in tag_to_ix.items()}
        predicted_tags = [ix_to_tag[ix.item()] for ix in tag_sequence]
        
        print("Predicted Tags:", predicted_tags)
        print("Actual Tags:   ", training_data[0][1])

# --- Main Execution ---
if __name__ == '__main__':
    train_model()
