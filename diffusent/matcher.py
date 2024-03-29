import torch
from scipy.optimize import linear_sum_assignment
from .lap import auction_lap
from torch import nn
import numpy as np
import os
os.environ["UDA_LAUNCH_BLOCKING"] = "1"

class HungarianMatcher(nn.Module):
    """This class computes an assignment between the targets and the predictions of the network
    For efficiency reasons, the targets don't include the no_object. Because of this, in general,
    there are more predictions than targets. In this case, we do a 1-to-1 matching of the best predictions,
    while the others are un-matched (and thus treated as non-objects).
    """

    def __init__(self, cost_class: float = 1, cost_span: float = 1, match_boundary_type = 'f1', solver = "hungarian"):
        """Creates the matcher
        Params:
            cost_class: This is the relative weight of the classification error in the matching cost
            cost_bbox: This is the relative weight of the L1 error of the bounding box coordinates in the matching cost
            cost_giou: This is the relative weight of the giou loss of the bounding box in the matching cost
        """
        super().__init__()
        self.cost_class = cost_class
        self.cost_span = cost_span
        self.match_boundary_type = match_boundary_type
        self.solver = solver

    @torch.no_grad()
    def forward(self, outputs, targets):
        """ Performs the matching
        Params:
            outputs: This is a dict that contains at least these entries:
                 "pred_logits": Tensor of dim [batch_size, num_queries, num_classes] with the classification logits
                 "pred_boxes": Tensor of dim [batch_size, num_queries, 4] with the predicted box coordinates
            targets: This is a list of targets (len(targets) = batch_size), where each target is a dict containing:
                 "labels": Tensor of dim [num_target_boxes] (where num_target_boxes is the number of ground-truth
                           objects in the target) containing the class labels
                 "boxes": Tensor of dim [num_target_boxes, 4] containing the target box coordinates
        Returns:
            A list of size batch_size, containing tuples of (index_i, index_j) where:
                - index_i is the indices of the selected predictions (in order)
                - index_j is the indices of the corresponding selected targets (in order)
            For each batch element, it holds:
                len(index_i) = len(index_j) = min(num_queries, num_target_boxes)
        """

        if self.solver == "order":
            sizes = targets["sizes"]
            indices = [(list(range(size)),list(range(size))) for size in sizes]
        else:
            bs, num_queries = outputs["pred_logits"].shape[:2]

            # We flatten to compute the cost matrices in a batch
            out_prob = outputs["pred_logits"].flatten(0, 1).softmax(dim=-1) # [batch_size * num_queries, 8]

            entity_left = outputs["pred_left"].flatten(0, 1)
            entity_right = outputs["pred_right"].flatten(0, 1) # [batch_size * num_queries]


            gt_ids = targets["labels"]
            gt_left = targets["gt_left"]
            gt_right = targets["gt_right"]
            
            # import pdb;pdb.set_trace()
            cost_class = -out_prob[:, gt_ids]            

            C = None

            # Final cost matrix
            if self.match_boundary_type == "f1":
                entity_left_idx = entity_left.argmax(dim=-1)  # [batch_size * num_queries]
                entity_right_idx = entity_right.argmax(dim=-1)  # [batch_size * num_queries]
                cost_dis = torch.abs(entity_left_idx.unsqueeze(-1) - gt_left.unsqueeze(0)) + torch.abs(entity_right_idx.unsqueeze(-1) - gt_right.unsqueeze(0))
                C = self.cost_span * cost_dis + self.cost_class * cost_class
            
            if self.match_boundary_type == "logp":
                cost_span = -(entity_left[:, gt_left] + entity_right[:, gt_right])
                C = self.cost_span * cost_span + self.cost_class * cost_class

            C = C.view(bs, num_queries, -1)

            sizes = targets["sizes"]
            indices = None
            # C_arr=C.cpu().numpy()
            # print(np.any(np.isinf(C_arr)),np.any(np.isnan(C_arr)))
            if self.solver == "hungarian":
                C = C.cpu()
                indices = [linear_sum_assignment(c[i]) for i, c in enumerate(C.split(sizes, -1))]
            if self.solver == "auction":
                indices = [auction_lap(c[i])[:2] for i, c in enumerate(C.split(sizes, -1))]

        return [(torch.as_tensor(i, dtype=torch.int64), torch.as_tensor(j, dtype=torch.int64)) for i, j in indices]

class HungarianMatcher_rel(nn.Module):
    """This class computes an assignment between the targets and the predictions of the network
    For efficiency reasons, the targets don't include the no_object. Because of this, in general,
    there are more predictions than targets. In this case, we do a 1-to-1 matching of the best predictions,
    while the others are un-matched (and thus treated as non-objects).
    """

    def __init__(self, cost_class: float = 1, cost_span: float = 1, match_boundary_type = 'f1', solver = "hungarian"):
        """Creates the matcher
        Params:
            cost_class: This is the relative weight of the classification error in the matching cost
            cost_bbox: This is the relative weight of the L1 error of the bounding box coordinates in the matching cost
            cost_giou: This is the relative weight of the giou loss of the bounding box in the matching cost
        """
        super().__init__()
        self.cost_class = cost_class
        self.cost_span = cost_span
        self.match_boundary_type = match_boundary_type
        self.solver = solver

    @torch.no_grad()
    def forward(self, outputs, targets):
        """ Performs the matching
        Params:
            outputs: This is a dict that contains at least these entries:
                 "pred_logits": Tensor of dim [batch_size, num_queries, num_classes] with the classification logits
                 "pred_boxes": Tensor of dim [batch_size, num_queries, 4] with the predicted box coordinates
            targets: This is a list of targets (len(targets) = batch_size), where each target is a dict containing:
                 "labels": Tensor of dim [num_target_boxes] (where num_target_boxes is the number of ground-truth
                           objects in the target) containing the class labels
                 "boxes": Tensor of dim [num_target_boxes, 4] containing the target box coordinates
        Returns:
            A list of size batch_size, containing tuples of (index_i, index_j) where:
                - index_i is the indices of the selected predictions (in order)
                - index_j is the indices of the corresponding selected targets (in order)
            For each batch element, it holds:
                len(index_i) = len(index_j) = min(num_queries, num_target_boxes)
        """

        if self.solver == "order":
            sizes = targets["sizes"]
            indices = [(list(range(size)),list(range(size))) for size in sizes]
        else:
            bs, num_queries = outputs["pred_logits"].shape[:2]

            # We flatten to compute the cost matrices in a batch
            out_prob = outputs["pred_logits"].flatten(0, 1).softmax(dim=-1) # [batch_size * num_queries, 8]

            entity_left_a = outputs["pred_left_a"].flatten(0, 1)
            entity_right_a = outputs["pred_right_a"].flatten(0, 1) # [batch_size * num_queries]
            entity_left_o = outputs["pred_left_o"].flatten(0, 1)
            entity_right_o = outputs["pred_right_o"].flatten(0, 1)

            gt_ids = targets["labels"]
            gt_left_a = targets["gt_left_a"]
            gt_right_a = targets["gt_right_a"]
            gt_left_o = targets["gt_left_o"]
            gt_right_o = targets["gt_right_o"]
            
            # import pdb;pdb.set_trace()
            cost_class = -out_prob[:, gt_ids]            

            C = None

            # Final cost matrix
            if self.match_boundary_type == "f1":
                entity_left_a_idx = entity_left_a.argmax(dim=-1)  # [batch_size * num_queries]
                entity_right_a_idx = entity_right_a.argmax(dim=-1)  # [batch_size * num_queries]
                entity_left_o_idx = entity_left_o.argmax(dim=-1)  # [batch_size * num_queries]
                entity_right_o_idx = entity_right_o.argmax(dim=-1)  # [batch_size * num_queries]
                cost_dis = torch.abs(entity_left_a_idx.unsqueeze(-1) - gt_left_a.unsqueeze(0)) + torch.abs(entity_right_a_idx.unsqueeze(-1) - gt_right_a.unsqueeze(0))+\
                        torch.abs(entity_left_o_idx.unsqueeze(-1) - gt_left_o.unsqueeze(0)) + torch.abs(entity_right_o_idx.unsqueeze(-1) - gt_right_o.unsqueeze(0))
                C = self.cost_span * cost_dis + self.cost_class * cost_class
            
            if self.match_boundary_type == "logp":
                # entity_left_a=entity_left_a.cpu()
                # gt_left_a=gt_left_a.cpu()
                # entity_right_a=entity_right_a.cpu()
                # gt_right_a=gt_right_a.cpu()
                # entity_left_o=entity_left_o.cpu()
                # gt_left_o=gt_left_o.cpu()
                # entity_right_o=entity_right_o.cpu()
                # gt_right_o=gt_right_o.cpu()
                # print(entity_left_a.shape, gt_left_a.shape, entity_right_a.shape, gt_right_a.shape, entity_left_o.shape, gt_left_o.shape, entity_right_o.shape, gt_right_o.shape)
                cost_span = -(entity_left_a[:, gt_left_a] + entity_right_a[:, gt_right_a]+entity_left_o[:, gt_left_o] + entity_right_o[:, gt_right_o])
                # entity_left_a=entity_left_a.to('cuda:0')
                # gt_left_a=gt_left_a.to('cuda:0')
                # entity_right_a=entity_right_a.to('cuda:0')
                # gt_right_a=gt_right_a.to('cuda:0')
                # entity_left_o=entity_left_o.to('cuda:0')
                # gt_left_o=gt_left_o.to('cuda:0')
                # entity_right_o=entity_right_o.to('cuda:0')
                # gt_right_o=gt_right_o.to('cuda:0')
                # cost_span=cost_span.to('cuda:0')
                C = self.cost_span * cost_span + self.cost_class * cost_class

            C = C.view(bs, num_queries, -1)

            sizes = targets["sizes"]
            indices = None
            
            if self.solver == "hungarian":
                C = C.cpu()
                indices = [linear_sum_assignment(c[i]) for i, c in enumerate(C.split(sizes, -1))]
            if self.solver == "auction":
                indices = [auction_lap(c[i])[:2] for i, c in enumerate(C.split(sizes, -1))]

        return [(torch.as_tensor(i, dtype=torch.int64), torch.as_tensor(j, dtype=torch.int64)) for i, j in indices]